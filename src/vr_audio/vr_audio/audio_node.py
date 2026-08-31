"""audio_node — mic capture and speaker playback (sounddevice).

Publishes /audio/raw (int16 mono 16 kHz, 32 ms blocks) and serves the Play
action on /audio/play. In duck mode (echo_mode: duck) capture is dropped
while the robot speaks. mock_audio (param or env VOCAL_ROBOT_MOCK_AUDIO=1)
runs the node without opening any audio hardware.
"""

import os
import queue
import threading
from pathlib import Path

import numpy as np
import rclpy
import yaml
from rclpy.action import ActionServer
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from vr_audio.playback import PlayTracker
from vr_interfaces.action import Play
from vr_interfaces.msg import AudioChunk

BLOCK_SAMPLES = 512          # 32 ms @ 16 kHz
FEEDBACK_STEP_S = 0.1        # ~10 Hz playback progress feedback


def _default_config_dir() -> str:
    return str(Path(__file__).resolve().parents[3] / "config")


class AudioNode(Node):
    def __init__(self):
        super().__init__("audio_node")
        self.declare_parameter("config_dir", os.environ.get("VOCAL_ROBOT_CONFIG_DIR", _default_config_dir()))
        self.declare_parameter("mock_audio", False)

        cfg = self._load_config()
        self._mock = bool(self.get_parameter("mock_audio").value) \
            or os.environ.get("VOCAL_ROBOT_MOCK_AUDIO") == "1"
        self._sample_rate = int(cfg.get("sample_rate", 16000))
        self._input_device = cfg.get("input_device", "default")
        self._output_device = cfg.get("output_device", "default")
        self._echo_mode = cfg.get("echo_mode", "duck")

        self._audio_pub = self.create_publisher(AudioChunk, "audio/raw", 10)
        self._capture_q: queue.Queue = queue.Queue(maxsize=256)
        self._playing = threading.Event()
        self._stream = None

        if self._mock:
            self.get_logger().warn("MOCK audio mode: mic/speaker NOT opened")
        else:
            self._open_capture()
            self.create_timer(0.02, self._drain_capture)

        self._play_server = ActionServer(
            self, Play, "audio/play", execute_callback=self._on_play,
            goal_callback=self._goal_ok, cancel_callback=self._cancel_ok)
        self.get_logger().info(
            f"audio_node ready (mock={self._mock}, echo_mode={self._echo_mode}, "
            f"in={self._input_device}, out={self._output_device})")

    def _load_config(self) -> dict:
        path = Path(self.get_parameter("config_dir").value) / "audio.yaml"
        with open(path) as f:
            return yaml.safe_load(f) or {}

    # ---- capture -----------------------------------------------------------

    def _open_capture(self):
        import sounddevice as sd

        self.get_logger().info(f"audio devices:\n{sd.query_devices()}")
        try:
            self._stream = sd.InputStream(
                device=self._input_device, samplerate=self._sample_rate,
                channels=1, dtype="int16", blocksize=BLOCK_SAMPLES,
                callback=self._capture_callback)
            self._stream.start()
        except Exception as exc:
            self.get_logger().error(
                f"failed to open input device {self._input_device!r}: {exc} — list devices "
                "with 'python -c \"import sounddevice as sd; print(sd.query_devices())\"'")
            raise

    def _capture_callback(self, indata, frames, time_info, status):
        # PortAudio thread: never block, hand off to the executor via queue
        try:
            self._capture_q.put_nowait(indata[:, 0])
        except queue.Full:
            pass  # executor busy; drop oldest audio rather than grow latency

    def _drain_capture(self):
        try:
            block = self._capture_q.get_nowait()
        except queue.Empty:
            return
        if self._echo_mode == "duck" and self._playing.is_set():
            return  # duck: mute capture while speaking
        msg = AudioChunk()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.samples = block.tolist()
        self._audio_pub.publish(msg)

    # ---- Play action -------------------------------------------------------

    def _goal_ok(self, goal_request):
        return rclpy.action.server.GoalResponse.ACCEPT

    def _cancel_ok(self, goal_handle):
        return rclpy.action.server.CancelResponse.ACCEPT

    def _on_play(self, goal_handle):
        import sounddevice as sd

        segments = [np.asarray(seg.samples, dtype=np.int16)
                    for seg in goal_handle.request.segments]
        rate = goal_handle.request.sample_rate or 24000
        tracker = PlayTracker([len(seg) for seg in segments])
        step = max(int(rate * FEEDBACK_STEP_S), 1)
        self._playing.set()
        result = Play.Result()

        try:
            if self._mock:
                self._play_segments(goal_handle, segments, step, tracker, out=None)
            else:
                with sd.OutputStream(device=self._output_device, samplerate=rate,
                                     channels=1, dtype="int16") as out:
                    out.start()
                    self._play_segments(goal_handle, segments, step, tracker, out)
            result.completed, result.last_segment_index, result.samples_played_in_last = tracker.result()
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
            else:
                goal_handle.succeed()
        except Exception as exc:
            self.get_logger().error(f"playback failed: {exc}")
            result.completed, result.last_segment_index, result.samples_played_in_last = tracker.result()
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
            else:
                goal_handle.abort()
        finally:
            self._playing.clear()
        return result

    def _play_segments(self, goal_handle, segments, step, tracker, out):
        for i, seg in enumerate(segments):
            pos = 0
            while pos < len(seg):
                if goal_handle.is_cancel_requested:
                    return
                n = min(step, len(seg) - pos)
                if out is not None:
                    out.write(seg[pos:pos + n])
                pos += n
                tracker.advance(n)
                feedback = Play.Feedback()
                feedback.segment_index = i
                feedback.samples_played = pos
                goal_handle.publish_feedback(feedback)


def main(args=None):
    rclpy.init(args=args)
    node = AudioNode()
    executor = MultiThreadedExecutor()  # capture timer + blocking Play execute run together
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

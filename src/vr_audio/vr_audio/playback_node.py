"""playback_node — speaker playback serving the Play action (worker-thread pattern).

rclpy runs synchronous callbacks inline on the executor's single event-loop
thread, so a blocking Play loop in an execute_callback would starve cancel
handling. Instead the goal is picked up in handle_accepted_callback and run
on a dedicated worker thread; the executor only ever does short callbacks
(goal accept, cancel flag, playing-state publication).

mock_audio (parameter or env VOCAL_ROBOT_MOCK_AUDIO=1) simulates playback
without a speaker.
"""

import os
import threading

import numpy as np
import rclpy
from rclpy.action import ActionServer, CancelResponse
from rclpy.node import Node
from std_msgs.msg import Bool

from vr_audio.playback import PlayTracker
from vr_interfaces.action import Play

FEEDBACK_STEP_S = 0.1        # ~10 Hz playback progress feedback


class PlaybackNode(Node):
    def __init__(self):
        super().__init__("playback_node")
        self.declare_parameter("output_device", "default")
        self.declare_parameter("mock_audio", False)

        self._mock = bool(self.get_parameter("mock_audio").value) \
            or os.environ.get("VOCAL_ROBOT_MOCK_AUDIO") == "1"
        self._output_device = self.get_parameter("output_device").value
        self._cancel_event = threading.Event()
        self._busy = threading.Event()   # one playback at a time

        self._playing_pub = self.create_publisher(Bool, "audio/playing", 10)
        self._publish_playing(False)

        self._server = ActionServer(
            self, Play, "audio/play",
            handle_accepted_callback=self._handle_accepted,
            cancel_callback=self._on_cancel)
        self.get_logger().info(
            f"playback_node ready (mock={self._mock}, out={self._output_device})")

    def _publish_playing(self, playing: bool):
        self._playing_pub.publish(Bool(data=playing))

    # ---- action callbacks (short; run on the executor) ---------------------

    def _handle_accepted(self, goal_handle):
        if self._busy.is_set():
            self.get_logger().warn("play goal rejected: speaker already in use")
            result = Play.Result()
            result.completed = False
            goal_handle.abort(result)
            return
        self.get_logger().info(
            f"play goal accepted ({len(goal_handle.request.segments)} segments)")
        threading.Thread(target=self._play_worker, args=(goal_handle,), daemon=True).start()

    def _on_cancel(self, goal_handle):
        self.get_logger().info("play cancel requested")
        self._cancel_event.set()
        return CancelResponse.ACCEPT

    # ---- worker thread (owns playback and the goal lifecycle) --------------

    def _play_worker(self, goal_handle):
        import sounddevice as sd

        self._cancel_event.clear()
        self._busy.set()
        # ACCEPTED -> EXECUTING. Note: goal_handle.execute() also calls
        # notify_execute(), which raises AttributeError when no execute
        # callback was registered; executing() is the bare state transition.
        if not goal_handle.is_cancel_requested:
            goal_handle.executing()
        self._publish_playing(True)

        segments = [np.asarray(seg.samples, dtype=np.int16)
                    for seg in goal_handle.request.segments]
        rate = goal_handle.request.sample_rate or 24000
        tracker = PlayTracker([len(seg) for seg in segments])
        step = max(int(rate * FEEDBACK_STEP_S), 1)
        result = Play.Result()
        error = None

        try:
            if self._mock:
                self._play_segments(goal_handle, segments, step, tracker, out=None)
            else:
                with sd.OutputStream(device=self._output_device, samplerate=rate,
                                     channels=1, dtype="int16") as out:
                    out.start()
                    self._play_segments(goal_handle, segments, step, tracker, out)
        except Exception as exc:
            error = exc
            self.get_logger().error(f"playback failed: {exc}")

        result.completed, result.last_segment_index, result.samples_played_in_last = tracker.result()
        try:
            if self._cancel_event.is_set() or goal_handle.is_cancel_requested:
                goal_handle.canceled(result)
            elif error is not None:
                goal_handle.abort(result)
            else:
                goal_handle.succeed(result)
        finally:
            self._publish_playing(False)
            self._busy.clear()

    def _play_segments(self, goal_handle, segments, step, tracker, out):
        for i, seg in enumerate(segments):
            pos = 0
            while pos < len(seg):
                if self._cancel_event.is_set() or goal_handle.is_cancel_requested:
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
    node = PlaybackNode()
    try:
        rclpy.spin(node)   # single-threaded executor suffices: callbacks never block
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

"""playback_node — speaker playback serving the Play action (timer-driven).

Playback runs as a timer-driven state machine entirely on the node's
single-threaded executor: every tick (50 ms by default) writes ~40 ms of
audio (20 % headroom against timer jitter; the PortAudio buffer absorbs the
rest). Cancel requests are therefore observed at most one period late, and
no thread ever blocks the executor.

mock_audio (parameter or env VOCAL_ROBOT_MOCK_AUDIO=1) plays at the same tick
cadence without a speaker, keeping mock tests timing-realistic.
"""

import os

import numpy as np
import rclpy
from rclpy.action import ActionServer, CancelResponse
from rclpy.node import Node
from std_msgs.msg import Bool

from vr_audio.playback import PlayTracker
from vr_interfaces.action import Play

CHUNK_RATIO = 0.8   # audio written per tick as a fraction of the period


class PlaybackNode(Node):
    def __init__(self):
        super().__init__("playback_node")
        self.declare_parameter("output_device", "default")
        self.declare_parameter("mock_audio", False)
        self.declare_parameter("tick_ms", 50)

        self._mock = bool(self.get_parameter("mock_audio").value) \
            or os.environ.get("VOCAL_ROBOT_MOCK_AUDIO") == "1"
        self._output_device = self.get_parameter("output_device").value
        self._tick_period = max(int(self.get_parameter("tick_ms").value), 10) / 1000.0

        # per-goal playback state (single in-flight goal; executor-owned)
        self._busy = False
        self._goal_handle = None
        self._segments = []
        self._tracker = None
        self._rate = 24000
        self._step = 1
        self._stream = None
        self._tick = None

        self._playing_pub = self.create_publisher(Bool, "audio/playing", 10)
        self._publish_playing(False)

        self._server = ActionServer(
            self, Play, "audio/play",
            handle_accepted_callback=self._handle_accepted,
            cancel_callback=self._on_cancel)
        self.get_logger().info(
            f"playback_node ready (mock={self._mock}, out={self._output_device}, "
            f"tick={self._tick_period * 1000:.0f}ms)")

    def _publish_playing(self, playing: bool):
        self._playing_pub.publish(Bool(data=playing))

    # ---- action callbacks (short; run on the executor) ---------------------

    def _handle_accepted(self, goal_handle):
        if self._busy:
            self.get_logger().warn("play goal rejected: speaker already in use")
            result = Play.Result()
            result.completed = False
            goal_handle.abort(result)
            return

        self._busy = True
        self._goal_handle = goal_handle
        self._segments = [np.asarray(seg.samples, dtype=np.int16)
                          for seg in goal_handle.request.segments]
        self._rate = goal_handle.request.sample_rate or 24000
        self._tracker = PlayTracker([len(seg) for seg in self._segments])
        self._step = max(int(self._rate * self._tick_period * CHUNK_RATIO), 1)

        # ACCEPTED -> EXECUTING. Note: goal_handle.execute() also calls
        # notify_execute(), which raises AttributeError when no execute
        # callback was registered; executing() is the bare state transition.
        if not goal_handle.is_cancel_requested:
            goal_handle.executing()

        if not self._mock:
            import sounddevice as sd

            self._stream = sd.OutputStream(
                device=self._output_device, samplerate=self._rate,
                channels=1, dtype="int16")
            self._stream.start()

        self._publish_playing(True)
        self.get_logger().info(f"play goal accepted ({len(self._segments)} segments)")
        self._tick = self.create_timer(self._tick_period, self._tick_playback)

    def _on_cancel(self, goal_handle):
        self.get_logger().info("play cancel requested")
        return CancelResponse.ACCEPT

    # ---- playback state machine (timer-driven, executor thread) ------------

    def _tick_playback(self):
        try:
            self._advance()
        except Exception as exc:
            self.get_logger().error(f"playback failed: {exc}")
            self._finalize("abort")

    def _advance(self):
        if self._goal_handle.is_cancel_requested:
            self._finalize("canceled")
            return
        if self._tracker.done:
            self._finalize("succeed")
            return

        if self._stream is not None:
            seg = self._segments[self._tracker.segment_index]
            pos = self._tracker.samples_in_segment
            n = min(self._step, len(seg) - pos)
            self._stream.write(seg[pos:pos + n])
        else:
            n = self._step
        self._tracker.advance(n)

        idx, played = self._tracker.feedback()
        feedback = Play.Feedback()
        feedback.segment_index = idx
        feedback.samples_played = played
        self._goal_handle.publish_feedback(feedback)

        if self._tracker.done:
            self._finalize("succeed")

    def _finalize(self, kind: str):
        if self._tick is not None:
            self._tick.cancel()   # safe from within its own callback
            self._tick = None
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        result = Play.Result()
        result.completed, result.last_segment_index, result.samples_played_in_last = \
            self._tracker.result()
        if kind == "succeed":
            self._goal_handle.succeed(result)
        elif kind == "canceled":
            self._goal_handle.canceled(result)
        else:
            self._goal_handle.abort(result)

        self._publish_playing(False)
        self._busy = False
        self._goal_handle = None
        self._segments = []
        self._tracker = None


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

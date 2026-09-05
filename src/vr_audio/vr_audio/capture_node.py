"""capture_node — microphone capture (sounddevice) publishing /audio/raw.

A minimal sensor node: the executor's 20 ms timer pulls 32 ms blocks from a
callback-free InputStream and publishes them. In duck mode (echo_mode: duck)
blocks are read and discarded while the robot speaks (per /audio/playing from
playback_node), keeping the PortAudio buffer fresh without publishing; in aec
mode capture keeps flowing (echo-cancel handles the loopback). mock_audio
(parameter or env VOCAL_ROBOT_MOCK_AUDIO=1) runs without opening the
microphone.

Timer-driven like playback_node: single-threaded executor, no callback
thread, no queue, and no DDS activity on any audio thread.
"""

import os
import sounddevice as sd

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from vr_interfaces.msg import AudioChunk

DISCARD_CAP = 8192   # max samples read-and-discarded per tick while ducking


class CaptureNode(Node):
    def __init__(self):
        super().__init__("capture_node")
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("channels", 1)
        self.declare_parameter("block_ms", 32)
        self.declare_parameter("input_device", "default")
        self.declare_parameter("mock_audio", False)
        self.declare_parameter("echo_mode", "duck")

        self._mock = bool(self.get_parameter("mock_audio").value) \
            or os.environ.get("VOCAL_ROBOT_MOCK_AUDIO") == "1"
        self._sample_rate = int(self.get_parameter("sample_rate").value)
        self._block_samples = int(self._sample_rate * int(self.get_parameter("block_ms").value) / 1000)
        self._input_device = self.get_parameter("input_device").value
        self._echo_mode = self.get_parameter("echo_mode").value
        self._playing = False

        self._audio_pub = self.create_publisher(AudioChunk, "audio/raw", 10)
        self.create_subscription(Bool, "audio/playing", self._on_playing, 10)

        if self._mock:
            self.get_logger().warn("MOCK capture: microphone NOT opened")
        else:
            self._open_capture()
        self.create_timer(0.02, self._pull)

        self.get_logger().info(
            f"capture_node ready (mock={self._mock}, echo_mode={self._echo_mode}, "
            f"in={self._input_device})")

    def _on_playing(self, msg: Bool):
        self._playing = msg.data

    def _open_capture(self):
        self.get_logger().info(f"audio devices:\n{sd.query_devices()}")
        try:
            self._stream = sd.InputStream(
                device=self._input_device, samplerate=self._sample_rate,
                channels=1, dtype="int16", blocksize=self._block_samples)
            self._stream.start()
        except Exception as exc:
            self.get_logger().error(
                f"failed to open input device {self._input_device!r}: {exc} — list devices "
                "with 'python -c \"import sounddevice as sd; print(sd.query_devices())\"'")
            raise

    def _pull(self):
        if self._mock:
            return
        try:
            available = self._stream.read_available
            if self._echo_mode == "duck" and self._playing:
                # duck: keep PortAudio's buffer fresh, publish nothing
                if available > 0:
                    self._stream.read(min(available, DISCARD_CAP))
                return
            if available < self._block_samples:
                return
            block = self._stream.read(self._block_samples)
        except Exception as exc:
            self.get_logger().error(f"capture failed: {exc}")
            return

        msg = AudioChunk()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.samples = block[0][:, 0].tolist()
        self._audio_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = CaptureNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

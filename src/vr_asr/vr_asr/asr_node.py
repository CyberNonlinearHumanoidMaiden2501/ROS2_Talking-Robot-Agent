"""asr_node — Silero VAD + faster-whisper transcription (M1). Stub for now."""

import rclpy
from rclpy.node import Node


class AsrNode(Node):
    def __init__(self):
        super().__init__("asr_node")
        self.get_logger().info("asr_node running (stub; M1: VAD + whisper)")


def main(args=None):
    rclpy.init(args=args)
    node = AsrNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

"""tts_node — text-to-speech via a swappable engine (M1). Stub for now."""

import rclpy
from rclpy.node import Node


class TtsNode(Node):
    def __init__(self):
        super().__init__("tts_node")
        self.get_logger().info("tts_node running (stub; M1: Kokoro Synthesize service)")


def main(args=None):
    rclpy.init(args=args)
    node = TtsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

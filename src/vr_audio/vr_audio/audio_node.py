"""audio_node — owns mic capture and speaker playback (M1). Stub for now."""

import rclpy
from rclpy.node import Node


class AudioNode(Node):
    def __init__(self):
        super().__init__("audio_node")
        self.get_logger().info("audio_node running (stub; M1: capture + playback)")


def main(args=None):
    rclpy.init(args=args)
    node = AudioNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

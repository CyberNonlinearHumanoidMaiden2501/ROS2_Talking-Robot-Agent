"""fast_llm_node — stateless adapter for the fast conversation model (M2). Stub."""

import rclpy
from rclpy.node import Node


class FastLlmNode(Node):
    def __init__(self):
        super().__init__("fast_llm_node")
        self.get_logger().info("fast_llm_node running (stub; M2: ChatFast service)")


def main(args=None):
    rclpy.init(args=args)
    node = FastLlmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

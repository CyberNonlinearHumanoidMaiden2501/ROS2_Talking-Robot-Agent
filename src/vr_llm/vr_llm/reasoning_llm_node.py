"""reasoning_llm_node — stateless adapter for the reasoning model (M3). Stub."""

import rclpy
from rclpy.node import Node


class ReasoningLlmNode(Node):
    def __init__(self):
        super().__init__("reasoning_llm_node")
        self.get_logger().info("reasoning_llm_node running (stub; M3: ReasoningTask action)")


def main(args=None):
    rclpy.init(args=args)
    node = ReasoningLlmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

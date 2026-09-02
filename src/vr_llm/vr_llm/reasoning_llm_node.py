"""reasoning_llm_node — stateless adapter for the reasoning model (M3). Stub."""

import rclpy
from rclpy.node import Node


class ReasoningLlmNode(Node):
    def __init__(self):
        super().__init__("reasoning_llm_node")
        # ROS parameters from vr_bringup/config/llm_nodes.yaml
        self.declare_parameter("base_url", "https://api.deepseek.com")
        self.declare_parameter("api_key_file", "")
        self.declare_parameter("model", "")
        self.declare_parameter("max_tokens", 8192)
        self.declare_parameter("temperature", 0.6)
        self.declare_parameter("timeout_s", 300)
        self.get_logger().info(f"reasoning_llm_node running (stub; M3: ReasoningTask action) "
                               f"model={self.get_parameter('model').value}")


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

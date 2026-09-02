"""fast_llm_node — stateless adapter for the fast conversation model (M2). Stub."""

import rclpy
from rclpy.node import Node


class FastLlmNode(Node):
    def __init__(self):
        super().__init__("fast_llm_node")
        # ROS parameters from vr_bringup/config/llm_nodes.yaml
        self.declare_parameter("base_url", "https://api.deepseek.com")
        self.declare_parameter("api_key_file", "")
        self.declare_parameter("model", "")
        self.declare_parameter("max_tokens", 1024)
        self.declare_parameter("temperature", 0.8)
        self.declare_parameter("timeout_s", 60)
        self.get_logger().info(f"fast_llm_node running (stub; M2: ChatFast service) "
                               f"model={self.get_parameter('model').value}")


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

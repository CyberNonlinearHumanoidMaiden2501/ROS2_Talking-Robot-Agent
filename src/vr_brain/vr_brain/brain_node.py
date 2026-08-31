"""brain_node — the conductor: state machine, conversation store, persona,
tool registry, barge-in and escalation (M2/M3). Stub for now."""

import rclpy
from rclpy.node import Node


class BrainNode(Node):
    def __init__(self):
        super().__init__("brain_node")
        self.get_logger().info("brain_node running (stub; M2: conversation core)")


def main(args=None):
    rclpy.init(args=args)
    node = BrainNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

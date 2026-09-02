"""tts_node — Synthesize service backed by a swappable engine (Kokoro in M1).

All settings are ROS parameters supplied by the launch file
(vr_bringup/config/tts_node.yaml).
"""

import rclpy
from rclpy.node import Node

from vr_interfaces.srv import Synthesize
from vr_tts.kokoro_engine import KokoroEngine


class TtsNode(Node):
    def __init__(self):
        super().__init__("tts_node")
        self.declare_parameter("engine", "kokoro")
        self.declare_parameter("voice_en", "af_heart")
        self.declare_parameter("voice_zh", "zf_001")

        self._engine = None  # lazy init on first request

        self._srv = self.create_service(Synthesize, "tts/synthesize", self._on_synthesize)
        self.get_logger().info(f"tts_node ready (engine: {self.get_parameter('engine').value})")

    def _ensure_engine(self):
        if self._engine is None:
            # init may download/load models; only trigger on demand
            self._engine = KokoroEngine(device=None)
        return self._engine

    def _on_synthesize(self, req, resp):
        engine = req.engine or self.get_parameter("engine").value
        if engine != "kokoro":
            resp.success = False
            resp.error = f"engine '{engine}' is not available in M1 (only 'kokoro')"
            return resp

        voice = req.voice or self.get_parameter("voice_en").value
        try:
            samples, rate = self._ensure_engine().synth(req.text, voice, req.speed or 1.0)
        except Exception as exc:  # surface model errors to the caller
            self.get_logger().error(f"synthesis failed: {exc}")
            resp.success = False
            resp.error = str(exc)
            return resp

        resp.samples = samples.tolist()
        resp.sample_rate = rate
        resp.success = True
        return resp


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

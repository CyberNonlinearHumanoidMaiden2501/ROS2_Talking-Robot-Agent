"""asr_node — transcribes finalized utterances from vad_node (faster-whisper).

Subscribes /asr/utterance_audio (int16 mono 16 kHz, one utterance per
message) and publishes /asr/utterance. Transcription runs synchronously in
the subscription callback: utterances arrive seconds apart and each takes a
few hundred ms on the GPU, so a single-threaded executor is sufficient —
no threads, no queues.
"""

import numpy as np
import rclpy
from rclpy.node import Node

from vr_asr.transcriber import Transcriber
from vr_interfaces.msg import AudioChunk, Utterance


class AsrNode(Node):
    def __init__(self):
        super().__init__("asr_node")
        self.declare_parameter("whisper_model", "medium")

        self.get_logger().info(f"loading whisper ({self.get_parameter('whisper_model').value}) ...")
        self._transcriber = Transcriber(model_size=self.get_parameter("whisper_model").value)
        self.get_logger().info("asr_node ready")

        self._utterance_pub = self.create_publisher(Utterance, "asr/utterance", 10)
        self.create_subscription(AudioChunk, "asr/utterance_audio", self._on_utterance, 10)

    def _on_utterance(self, msg: AudioChunk):
        audio = np.asarray(msg.samples, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            result = self._transcriber.transcribe(audio)
        except Exception as exc:
            self.get_logger().error(f"transcription failed: {exc}")
            return
        if not result["text"]:
            return

        out = Utterance()
        out.header.stamp = msg.header.stamp
        out.text = result["text"]
        out.language = result["language"]
        out.confidence = float(result["confidence"])
        self._utterance_pub.publish(out)
        self.get_logger().info(f"utterance [{out.language}] conf={out.confidence:.2f}: {out.text}")


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

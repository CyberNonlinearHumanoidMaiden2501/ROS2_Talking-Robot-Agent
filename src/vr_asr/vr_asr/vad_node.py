"""vad_node — Silero VAD + utterance segmentation (auxiliary to asr_node).

Subscribes /audio/raw (int16 mono 16 kHz blocks) and publishes
/asr/speech_state every block. When an utterance finalizes (end-of-speech
silence reached), its trimmed audio is published once on
/asr/utterance_audio for asr_node to transcribe.

Single-threaded executor suffices: every callback is short (Silero evaluates
one 32 ms block in well under a millisecond).
"""

import numpy as np
import rclpy
from rclpy.node import Node

from vr_asr.vad_engine import BLOCK_SAMPLES, UtteranceSegmenter
from vr_interfaces.msg import AudioChunk, SpeechState


class VadNode(Node):
    def __init__(self):
        super().__init__("vad_node")
        self.declare_parameter("vad.threshold", 0.5)
        self.declare_parameter("vad.min_speech_ms", 250)
        self.declare_parameter("vad.end_silence_ms", 600)
        self.declare_parameter("vad.max_utterance_ms", 30000)

        self.get_logger().info("loading silero VAD ...")
        self._segmenter = UtteranceSegmenter(
            threshold=float(self.get_parameter("vad.threshold").value),
            min_speech_ms=int(self.get_parameter("vad.min_speech_ms").value),
            end_silence_ms=int(self.get_parameter("vad.end_silence_ms").value),
            max_utterance_ms=int(self.get_parameter("vad.max_utterance_ms").value),
        )
        self.get_logger().info("vad_node ready")

        self._speech_pub = self.create_publisher(SpeechState, "asr/speech_state", 10)
        self._utterance_pub = self.create_publisher(AudioChunk, "asr/utterance_audio", 10)
        self.create_subscription(AudioChunk, "audio/raw", self._on_audio, 10)

    def _on_audio(self, msg: AudioChunk):
        block = np.asarray(msg.samples, dtype=np.int16).astype(np.float32) / 32768.0
        if block.size != BLOCK_SAMPLES:
            return  # partial/resized blocks are ignored

        utterance = self._segmenter.process(block)

        state = SpeechState()
        state.header = msg.header
        state.is_speech = self._segmenter.is_speech
        self._speech_pub.publish(state)

        if utterance is not None:
            out = AudioChunk()
            out.header.stamp = self.get_clock().now().to_msg()
            out.samples = (np.clip(utterance, -1.0, 1.0) * 32767.0).astype(np.int16).tolist()
            self._utterance_pub.publish(out)
            self.get_logger().info(f"utterance segment: {len(out.samples) / 16000:.2f}s")


def main(args=None):
    rclpy.init(args=args)
    node = VadNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()

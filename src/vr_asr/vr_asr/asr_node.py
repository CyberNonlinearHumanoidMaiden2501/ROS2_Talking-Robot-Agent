"""asr_node — transcribes finalized utterances from vad_node (Qwen3-ASR).

Subscribes /asr/utterance_audio (int16 mono 16 kHz, one utterance per
message) and publishes /asr/utterance. Transcription runs synchronously in
the subscription callback: utterances arrive seconds apart and each takes a
few hundred ms on the GPU, so a single-threaded executor is sufficient —
no threads, no queues.
"""

import numpy as np
import rclpy
import torch
from rclpy.node import Node

from vr_interfaces.msg import AudioChunk, Utterance

LANG_CODES = {
    "English": "en",
    "Chinese": "zh",
    "Cantonese": "yue",
    "Japanese": "ja",
    "Korean": "ko",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Russian": "ru",
}


class AsrNode(Node):
    def __init__(self):
        super().__init__("asr_node")
        self.declare_parameter("asr_model", "Qwen/Qwen3-ASR-0.6B-hf")
        self.declare_parameter("device", "cuda")
        self.declare_parameter("dtype", "bfloat16")
        self.declare_parameter("max_new_tokens", 256)

        model_id = self.get_parameter("asr_model").value
        device = self.get_parameter("device").value
        dtype = getattr(torch, self.get_parameter("dtype").value)

        self.get_logger().info(f"loading Qwen3-ASR ({model_id}) ...")
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        self._processor = AutoProcessor.from_pretrained(model_id)
        self._model = AutoModelForMultimodalLM.from_pretrained(
            model_id, device_map=device, dtype=dtype).eval()
        self.get_logger().info(f"qwen3-asr ready: {model_id} on {device}")

        self._utterance_pub = self.create_publisher(Utterance, "asr/utterance", 10)
        self.create_subscription(AudioChunk, "asr/utterance_audio", self._on_utterance, 10)

    def _transcribe(self, audio: np.ndarray) -> dict:
        """audio: float32 mono 16 kHz. Returns {text, language, confidence}."""
        # audio must be 1-D (T,): the processor treats 2-D arrays as batches
        inputs = self._processor.apply_transcription_request(
            audio=audio,
            processor_kwargs={"sampling_rate": 16000},
            language=None,
        ).to(self._model.device, self._model.dtype)

        with torch.inference_mode():
            output = self._model.generate(
                **inputs,
                max_new_tokens=int(self.get_parameter("max_new_tokens").value),
                do_sample=False,
                output_scores=True,
                return_dict_in_generate=True,
            )
        generated = output.sequences[:, inputs["input_ids"].shape[1]:]

        parsed = self._processor.decode(generated, return_format="parsed")[0]
        text = self._processor.decode(generated, return_format="transcription_only")[0]

        # mean probability of the generated tokens as the confidence scalar
        transition = self._model.compute_transition_scores(
            output.sequences, output.scores, normalize_logits=True
        )
        confidence = float(transition.exp().mean().item())

        lang_name = parsed.get("language") if isinstance(parsed, dict) else None
        return {
            "text": text.strip(),
            "language": LANG_CODES.get(lang_name, ""),
            "confidence": confidence,
        }

    def _on_utterance(self, msg: AudioChunk):
        audio = np.asarray(msg.samples, dtype=np.int16).astype(np.float32) / 32768.0
        try:
            result = self._transcribe(audio)
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

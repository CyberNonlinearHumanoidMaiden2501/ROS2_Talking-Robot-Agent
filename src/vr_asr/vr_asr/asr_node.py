"""asr_node — Silero VAD + faster-whisper (bilingual en/zh).

Subscribes /audio/raw (int16 mono 16 kHz blocks), publishes /asr/speech_state
every block and /asr/utterance when a finalized utterance is transcribed.
Transcription runs in a worker thread so VAD never blocks.
"""

import os
import queue
import threading
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
import yaml

from vr_asr.transcriber import Transcriber
from vr_asr.vad_engine import BLOCK_SAMPLES, UtteranceSegmenter
from vr_interfaces.msg import AudioChunk, SpeechState, Utterance


def _default_config_dir() -> str:
    return str(Path(__file__).resolve().parents[3] / "config")


class AsrNode(Node):
    def __init__(self):
        super().__init__("asr_node")
        self.declare_parameter("config_dir", os.environ.get("VOCAL_ROBOT_CONFIG_DIR", _default_config_dir()))
        self.declare_parameter("whisper_model", "medium")

        vad_cfg = self._load_vad_config()
        self.get_logger().info(f"loading silero VAD + whisper ({self.get_parameter('whisper_model').value})...")
        self._segmenter = UtteranceSegmenter(**vad_cfg)
        self._transcriber = Transcriber(model_size=self.get_parameter("whisper_model").value)
        self.get_logger().info("asr_node ready")

        self._speech_pub = self.create_publisher(SpeechState, "asr/speech_state", 10)
        self._utterance_pub = self.create_publisher(Utterance, "asr/utterance", 10)
        self.create_subscription(AudioChunk, "audio/raw", self._on_audio, 10)

        self._jobs: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._worker.start()

    def _load_vad_config(self) -> dict:
        path = Path(self.get_parameter("config_dir").value) / "audio.yaml"
        with open(path) as f:
            cfg = yaml.safe_load(f)
        vad = cfg.get("vad", {})
        return {
            "threshold": vad.get("threshold", 0.5),
            "min_speech_ms": vad.get("min_speech_ms", 250),
            "end_silence_ms": vad.get("end_silence_ms", 600),
            "max_utterance_ms": vad.get("max_utterance_ms", 30000),
        }

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
            self._jobs.put(utterance)

    def _transcribe_loop(self):
        while rclpy.ok():
            try:
                audio = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                result = self._transcriber.transcribe(audio)
            except Exception as exc:
                self.get_logger().error(f"transcription failed: {exc}")
                continue
            if not result["text"]:
                continue
            msg = Utterance()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.text = result["text"]
            msg.language = result["language"]
            msg.confidence = float(result["confidence"])
            self._utterance_pub.publish(msg)
            self.get_logger().info(f"utterance [{msg.language}] conf={msg.confidence:.2f}: {msg.text}")


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

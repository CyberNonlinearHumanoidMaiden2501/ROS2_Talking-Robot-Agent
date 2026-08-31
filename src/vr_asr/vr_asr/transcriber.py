"""faster-whisper transcription worker (file-testable, no ROS deps)."""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger("vr_asr.transcriber")


class Transcriber:
    """Bilingual (en/zh) transcriber. CUDA int8_float16 preferred, CPU int8
    fallback if GPU init fails."""

    def __init__(self, model_size="medium", device="cuda", compute_type="int8_float16"):
        from faster_whisper import WhisperModel

        for dev, ct in ((device, compute_type), ("cpu", "int8")):
            try:
                self._model = WhisperModel(model_size, device=dev, compute_type=ct)
                log.info("whisper ready: %s on %s/%s", model_size, dev, ct)
                break
            except Exception as exc:
                log.warning("whisper init failed on %s/%s: %s", dev, ct, exc)
        else:
            raise RuntimeError("whisper model failed to initialize on any device")

    def transcribe(self, audio: np.ndarray) -> dict:
        """audio: float32 mono 16 kHz. Returns {text, language, confidence}."""
        segments, info = self._model.transcribe(
            audio.astype(np.float32), language=None, beam_size=5
        )
        parts, logprobs = [], []
        for seg in segments:
            text = seg.text.strip()
            if text:
                parts.append(text)
                logprobs.append(seg.avg_logprob)
        confidence = float(np.exp(np.mean(logprobs))) if logprobs else 0.0
        return {
            "text": " ".join(parts).strip(),
            "language": info.language or "",
            "confidence": confidence,
        }

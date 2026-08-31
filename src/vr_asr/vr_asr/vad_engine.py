"""Silero VAD wrapper + utterance segmentation state machine (file-testable)."""

from __future__ import annotations

import numpy as np
import torch

SAMPLE_RATE = 16000
BLOCK_SAMPLES = 512  # 32 ms; silero's required block size at 16 kHz


class UtteranceSegmenter:
    """Feed 512-sample float32 blocks via process(); it returns a finalized
    utterance (float32 array, trailing silence trimmed) or None.

    State machine: silence -> speech on prob >= threshold; speech -> silence
    once trailing silence reaches end_silence_ms, then the utterance is
    finalized. Utterances shorter than min_speech_ms are discarded as noise.
    A max_utterance_ms guard finalizes runaway speech (e.g. loud music).
    """

    def __init__(self, threshold=0.5, min_speech_ms=250, end_silence_ms=600,
                 max_utterance_ms=30000):
        from silero_vad import load_silero_vad

        self._model = load_silero_vad()
        self.threshold = threshold
        self.min_speech_samples = int(min_speech_ms * SAMPLE_RATE / 1000)
        self.end_silence_samples = int(end_silence_ms * SAMPLE_RATE / 1000)
        self.max_speech_samples = int(max_utterance_ms * SAMPLE_RATE / 1000)

        self._buf: list[np.ndarray] = []
        self._speech_samples = 0
        self._silence_samples = 0
        self.is_speech = False

    def _prob(self, block: np.ndarray) -> float:
        with torch.inference_mode():
            return float(self._model(torch.from_numpy(block), SAMPLE_RATE))

    def process(self, block: np.ndarray) -> np.ndarray | None:
        """Feed one block; returns a finalized utterance or None."""
        prob = self._prob(block)
        utterance = None

        if self.is_speech:
            self._buf.append(block)
            if prob >= self.threshold:
                self._speech_samples += BLOCK_SAMPLES
                self._silence_samples = 0
            else:
                self._silence_samples += BLOCK_SAMPLES
                if (self._silence_samples >= self.end_silence_samples
                        or self._speech_samples >= self.max_speech_samples):
                    utterance = self._finalize()
        elif prob >= self.threshold:
            self.is_speech = True
            self._buf = [block]
            self._speech_samples = BLOCK_SAMPLES
            self._silence_samples = 0

        return utterance

    def _finalize(self) -> np.ndarray | None:
        audio = np.concatenate(self._buf).astype(np.float32)
        keep = self._speech_samples
        self._buf = []
        self._speech_samples = 0
        self._silence_samples = 0
        self.is_speech = False
        if keep < self.min_speech_samples:
            return None  # too short: treat as noise
        return audio[:keep]

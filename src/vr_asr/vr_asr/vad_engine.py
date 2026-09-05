"""Silero VAD sliding-window segmenter (file-testable)."""

from __future__ import annotations

import numpy as np
import torch

SAMPLE_RATE = 16000
BLOCK_SAMPLES = 512  # 32 ms; silero's required block size at 16 kHz


class UtteranceSegmenter:
    """Emits fixed-length audio windows while speech is detected.

    Keeps a rolling window of `window_blocks` blocks (audio + probabilities).
    When the mean probability of the oldest `prob_blocks` probs exceeds the
    threshold, the whole window is emitted and the state resets — consecutive
    windows are disjoint and together cover the speech.
    """

    def __init__(self, threshold=0.5, window_blocks=6, prob_blocks=3):
        from silero_vad import load_silero_vad

        self._model = load_silero_vad()
        self.threshold = threshold
        self.window_blocks = int(window_blocks)
        self.prob_blocks = min(int(prob_blocks), self.window_blocks)
        self._buf = [np.zeros(BLOCK_SAMPLES, dtype=np.float32) for _ in range(self.window_blocks)]
        self._prob_buf = [0.0] * self.window_blocks

    def _prob(self, block: np.ndarray) -> float:
        with torch.inference_mode():
            return float(self._model(torch.from_numpy(block), SAMPLE_RATE))

    def process(self, block: np.ndarray) -> np.ndarray | None:
        """Feed one block; returns a window of audio when speech is detected."""
        self._buf.append(block)
        self._buf.pop(0)
        self._prob_buf.append(self._prob(block))
        self._prob_buf.pop(0)

        if np.mean(self._prob_buf[: self.prob_blocks]) > self.threshold:
            audio = np.concatenate(self._buf).astype(np.float32)
            self._buf = [np.zeros(BLOCK_SAMPLES, dtype=np.float32) for _ in range(self.window_blocks)]
            self._prob_buf = [0.0] * self.window_blocks
            return audio
        return None

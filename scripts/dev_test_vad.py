"""Dev test (software-only): sliding-window VAD on silence vs synthesized speech."""

import sys
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "vr_asr"))
sys.path.insert(0, str(REPO / "src" / "vr_tts"))

from vr_asr.vad_engine import BLOCK_SAMPLES, SAMPLE_RATE, UtteranceSegmenter  # noqa: E402
from vr_tts.kokoro_engine import KokoroEngine  # noqa: E402


def feed(segmenter, audio: np.ndarray):
    """Feed audio in 512-sample blocks; return emitted windows."""
    windows = []
    n = len(audio) // BLOCK_SAMPLES * BLOCK_SAMPLES
    for i in range(0, n, BLOCK_SAMPLES):
        window = segmenter.process(audio[i:i + BLOCK_SAMPLES])
        if window is not None:
            windows.append(window)
    return windows


def main():
    ok = True

    # 1. silence must not produce windows
    seg = UtteranceSegmenter()
    silence = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    utts = feed(seg, silence)
    passed = len(utts) == 0
    ok &= passed
    print(f"[silence] {'PASS' if passed else 'FAIL'}  windows={len(utts)}")

    # 2. speech must produce disjoint ~192 ms windows covering the speech
    engine = KokoroEngine(device=None)
    samples, rate = engine.synth("This is a voice activity detection test.", "af_heart")
    speech16 = resample_poly(samples.astype(np.float32), 2, 3) / 32768.0  # 24k int16 -> 16k float
    pad = np.zeros(int(0.8 * SAMPLE_RATE), dtype=np.float32)
    padded = np.concatenate([pad, speech16, pad])

    seg2 = UtteranceSegmenter()
    utts2 = feed(seg2, padded)
    total = sum(len(w) for w in utts2)
    max_window = seg2.window_blocks * BLOCK_SAMPLES
    passed = (len(utts2) >= 3
              and all(len(w) <= max_window for w in utts2)
              and total >= 0.8 * len(speech16))
    ok &= passed
    print(f"[speech] {'PASS' if passed else 'FAIL'}  windows={len(utts2)} "
          f"covered={total / SAMPLE_RATE * 1000:.0f}ms (speech ~{len(speech16) / SAMPLE_RATE * 1000:.0f}ms)")

    print("VAD", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

"""Dev test (software-only): VAD segmentation on silence vs synthesized speech."""

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
    """Feed audio in 512-sample blocks; return finalized utterances."""
    utterances = []
    n = len(audio) // BLOCK_SAMPLES * BLOCK_SAMPLES
    for i in range(0, n, BLOCK_SAMPLES):
        utt = segmenter.process(audio[i:i + BLOCK_SAMPLES])
        if utt is not None:
            utterances.append(utt)
    return utterances


def main():
    ok = True

    # 1. silence must not produce utterances
    seg = UtteranceSegmenter(min_speech_ms=250, end_silence_ms=600)
    silence = np.zeros(SAMPLE_RATE * 3, dtype=np.float32)
    utts = feed(seg, silence)
    passed = len(utts) == 0 and not seg.is_speech
    ok &= passed
    print(f"[silence] {'PASS' if passed else 'FAIL'}  utterances={len(utts)}")

    # 2. synthesized speech must produce exactly one utterance (~speech-mask length)
    engine = KokoroEngine(device=None)
    samples, rate = engine.synth("This is a voice activity detection test.", "af_heart")
    speech16 = resample_poly(samples.astype(np.float32), 2, 3) / 32768.0  # 24k int16 -> 16k float
    pad = np.zeros(int(0.8 * SAMPLE_RATE), dtype=np.float32)  # > end_silence_ms
    padded = np.concatenate([pad, speech16, pad])

    # ground truth: count speech blocks with the raw VAD model (no state machine)
    import torch
    from silero_vad import load_silero_vad
    model = load_silero_vad()
    mask_ms = 0.0
    n = len(padded) // BLOCK_SAMPLES * BLOCK_SAMPLES
    for i in range(0, n, BLOCK_SAMPLES):
        with torch.inference_mode():
            p = float(model(torch.from_numpy(padded[i:i + BLOCK_SAMPLES]), SAMPLE_RATE))
        if p >= 0.5:
            mask_ms += BLOCK_SAMPLES / SAMPLE_RATE * 1000

    seg2 = UtteranceSegmenter(min_speech_ms=250, end_silence_ms=600)
    utts2 = feed(seg2, padded)
    detected_ms = len(utts2[0]) / SAMPLE_RATE * 1000 if utts2 else 0.0
    # segmenter must capture the speech (allow small trailing-trim differences)
    passed = len(utts2) == 1 and detected_ms >= 0.8 * mask_ms and detected_ms <= mask_ms + 400
    ok &= passed
    print(f"[speech] {'PASS' if passed else 'FAIL'}  utterances={len(utts2)} "
          f"(speech mask ~{mask_ms:.0f}ms, detected {detected_ms:.0f}ms)")

    print("VAD", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

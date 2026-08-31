"""Dev test (software-only): Kokoro TTS -> WAV -> Whisper round-trip, en + zh.

Verifies both halves of the M1 voice pipeline without touching hardware:
synthesis quality (Whisper can re-recognize the generated speech) and
bilingual transcription (auto language detection).
"""

import difflib
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "vr_tts"))
sys.path.insert(0, str(REPO / "src" / "vr_asr"))

from vr_asr.transcriber import Transcriber  # noqa: E402
from vr_tts.kokoro_engine import KokoroEngine  # noqa: E402

CASES = [
    ("en", "af_heart", "The quick brown fox jumps over the lazy dog.",
     "the quick brown fox jumps over the lazy dog", 0.7),
    ("zh", "zf_001", "今天天气很好，我们一起去公园散步吧。",
     "今天天气很好我们一起去公园散步吧", 0.6),
]


def normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def main():
    engine = KokoroEngine(device=None)
    transcriber = Transcriber(model_size="medium")
    ok = True

    for lang, voice, text, expected, min_ratio in CASES:
        samples, rate = engine.synth(text, voice)
        audio16 = resample_poly(samples.astype(np.float32), 2, 3) / 32768.0  # 24k int16 -> 16k float
        wav_path = f"/tmp/roundtrip_{lang}.wav"
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes((np.clip(audio16, -1, 1) * 32767).astype(np.int16).tobytes())

        result = transcriber.transcribe(audio16)
        ratio = difflib.SequenceMatcher(None, normalize(result["text"]), normalize(expected)).ratio()
        passed = ratio >= min_ratio
        ok &= passed
        print(f"[{lang}] {'PASS' if passed else 'FAIL'}  ratio={ratio:.2f}  "
              f"detected_lang={result['language']}  wav={wav_path}")
        print(f"    expected: {expected}")
        print(f"    heard   : {result['text']}")

    print("ROUNDTRIP", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

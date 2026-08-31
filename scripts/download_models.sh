#!/usr/bin/env bash
# Downloads the model weights used by the local nodes (run during M1).
# Whisper "small" (multilingual en/zh), Kokoro TTS, Silero VAD.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate

python3 - <<'PY'
from faster_whisper import WhisperModel
print("[1/3] faster-whisper small (multilingual) ...")
try:
    WhisperModel("small", device="cuda", compute_type="int8_float16")
    print("  -> small on CUDA OK")
except Exception as e:
    print("  CUDA unavailable (%s); falling back to CPU int8" % e)
    WhisperModel("small", device="cpu", compute_type="int8")

print("[2/3] kokoro TTS ...")
from kokoro import KPipeline
for lang in ("a", "z"):   # a = english voices, z = mandarin voices
    KPipeline(lang_code=lang)
print("  -> kokoro OK")

print("[3/3] silero VAD ...")
from silero_vad import load_silero_vad
load_silero_vad()
print("  -> silero OK")
PY
echo "models downloaded."

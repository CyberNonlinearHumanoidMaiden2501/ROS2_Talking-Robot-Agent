#!/usr/bin/env bash
# Downloads model weights used by the local nodes (M1+).
# Whisper "medium" (multilingual en/zh), Kokoro TTS (en + zh checkpoints and
# default voices). Silero VAD ships inside the silero-vad wheel — no download.
set -eo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"

python3 - <<'PY'
from faster_whisper import WhisperModel
print("[1/2] faster-whisper medium (multilingual) ...")
try:
    WhisperModel("medium", device="cuda", compute_type="int8_float16")
    print("  -> medium on CUDA OK")
except Exception as e:
    print("  CUDA unavailable (%s); falling back to CPU int8" % e)
    WhisperModel("medium", device="cpu", compute_type="int8")

print("[2/2] kokoro TTS (en + zh checkpoints and voices) ...")
from kokoro import KPipeline
for lang, repo, voice, text in (
    ("a", None, "af_heart", "Model download test."),
    ("z", "hexgrad/Kokoro-82M-v1.1-zh", "zf_001", "模型下载测试。"),
):
    pipe = KPipeline(lang_code=lang, repo_id=repo)
    next(pipe(text, voice=voice, speed=1.0))
    print(f"  -> kokoro {lang} ({voice}) OK")
PY
echo "models downloaded."

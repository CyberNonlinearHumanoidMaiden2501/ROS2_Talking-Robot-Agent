#!/usr/bin/env bash
# Downloads model weights used by the local nodes (M1+).
# Qwen3-ASR 0.6B (bilingual en/zh transcription), Kokoro TTS (en + zh
# checkpoints and default voices). Silero VAD ships inside the silero-vad
# wheel — no download.
set -eo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"

python3 - <<'PY'
print("[1/2] Qwen3-ASR (Qwen/Qwen3-ASR-0.6B-hf) ...")
import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor
AutoProcessor.from_pretrained("Qwen/Qwen3-ASR-0.6B-hf")
AutoModelForMultimodalLM.from_pretrained(
    "Qwen/Qwen3-ASR-0.6B-hf", device_map="cpu", dtype=torch.bfloat16)
print("  -> Qwen3-ASR OK")

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

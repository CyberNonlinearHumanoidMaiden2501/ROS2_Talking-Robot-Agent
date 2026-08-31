#!/usr/bin/env bash
# Creates .venv with uv (--system-site-packages so rclpy from /opt/ros/jazzy is
# reachable after sourcing ROS2; PEP 668 forbids pip on the system python),
# then installs runtime Python dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found; install it first (https://docs.astral.sh/uv/)" >&2
    exit 1
fi

# Recreate if missing OR if system-site-packages got disabled (needed for
# ROS2 system deps like lark when generators run under the venv python).
if [ ! -x .venv/bin/python ] || ! grep -q "include-system-site-packages = true" .venv/pyvenv.cfg 2>/dev/null; then
    rm -rf .venv   # clear any half-created venv from a previous failed run
    uv venv --system-site-packages .venv
fi

uv pip install --python .venv/bin/python --upgrade pip setuptools wheel
# CUDA 12 runtime for ctranslate2/whisper (torch wheels are CUDA 13).
uv pip install --python .venv/bin/python \
    colcon-common-extensions \
    pyyaml numpy sounddevice openai \
    faster-whisper==1.2.1 \
    silero-vad==6.2.1 \
    kokoro==0.9.4 \
    "misaki[zh]" \
    scipy \
    nvidia-cublas-cu12 \
    nvidia-cudnn-cu12 \
    nvidia-cuda-runtime-cu12 \
    onnxruntime \
    duckduckgo_search

echo "venv ready. Verify with: .venv/bin/python -c 'import torch, faster_whisper, kokoro, silero_vad'"

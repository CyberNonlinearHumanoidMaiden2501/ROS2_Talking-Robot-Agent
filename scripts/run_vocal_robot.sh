#!/usr/bin/env bash
# Launches the full vocal-robot stack.
# NOTE: no `set -u` — /opt/ros/jazzy/setup.bash references
# AMENT_TRACE_SETUP_FILES unguarded and breaks under nounset.
set -eo pipefail
cd "$(dirname "$0")/.."

source /opt/ros/jazzy/setup.bash
source install/setup.bash
export PATH="$PWD/.venv/bin:$PATH"   # uv venv ships no activate script
# ctranslate2 (whisper GPU) is built for CUDA 12 while torch ships CUDA 13
# libs; expose the pip-installed CUDA 12 runtime so libcublas.so.12 resolves.
NV_LIBS="$PWD/.venv/lib/python3.12/site-packages/nvidia"
export LD_LIBRARY_PATH="$NV_LIBS/cublas/lib:$NV_LIBS/cudnn/lib:$NV_LIBS/cuda_runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# Models are pre-downloaded (scripts/download_models.sh); skip HF network
# lookups at runtime — they can stall for minutes on a slow connection.
export HF_HUB_OFFLINE=1
exec ros2 launch vr_bringup vocal_robot.launch.py

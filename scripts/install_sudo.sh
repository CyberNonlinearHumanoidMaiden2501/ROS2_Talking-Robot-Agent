#!/usr/bin/env bash
# One-time privileged setup for vocal-robot (M0).
# Run once: bash scripts/install_sudo.sh
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
    python3-venv \
    python3-colcon-common-extensions \
    python3-rosdep2 \
    ffmpeg \
    portaudio19-dev \
    pulseaudio-utils

sudo rosdep init 2>/dev/null || true   # already initialized on some systems
rosdep update
echo "sudo setup complete."

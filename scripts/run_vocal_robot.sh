#!/usr/bin/env bash
# Launches the full vocal-robot stack.
# NOTE: no `set -u` — /opt/ros/jazzy/setup.bash references
# AMENT_TRACE_SETUP_FILES unguarded and breaks under nounset.
set -eo pipefail
cd "$(dirname "$0")/.."

source /opt/ros/jazzy/setup.bash
source install/setup.bash
export PATH="$PWD/.venv/bin:$PATH"   # uv venv ships no activate script
exec ros2 launch vr_bringup vocal_robot.launch.py

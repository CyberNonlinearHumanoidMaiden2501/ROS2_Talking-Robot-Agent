#!/usr/bin/env bash
# Builds the workspace. ROS2 is sourced first so colcon can find
# ament_cmake/rosidl; the venv python is preferred for generated entry points
# while rclpy stays reachable via PYTHONPATH.
# NOTE: no `set -u` — /opt/ros/jazzy/setup.bash references
# AMENT_TRACE_SETUP_FILES unguarded and breaks under nounset.
set -eo pipefail
cd "$(dirname "$0")/.."

source /opt/ros/jazzy/setup.bash
# uv venvs ship no activate script; PATH order is enough for colcon and
# generated entry points. rclpy stays reachable via PYTHONPATH.
export PATH="$PWD/.venv/bin:$PATH"

colcon build --symlink-install

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config_dir = Path(get_package_share_directory("vr_bringup")) / "config"

    return LaunchDescription([
        Node(package="vr_audio", executable="capture_node", name="capture_node",
             output="screen", parameters=[str(config_dir / "capture_node.yaml")]),
        Node(package="vr_asr", executable="vad_node", name="vad_node",
             output="screen", parameters=[str(config_dir / "vad_node.yaml")]),
        Node(package="vr_asr", executable="asr_node", name="asr_node",
             output="screen", parameters=[str(config_dir / "asr_node.yaml")]),
    ])

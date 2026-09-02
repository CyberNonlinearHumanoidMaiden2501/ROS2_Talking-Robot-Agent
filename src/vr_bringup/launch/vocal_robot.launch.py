from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config_dir = Path(get_package_share_directory("vr_bringup")) / "config"

    return LaunchDescription([
        Node(package="vr_audio", executable="capture_node", name="capture_node",
             output="screen", parameters=[str(config_dir / "capture_node.yaml")]),
        Node(package="vr_audio", executable="playback_node", name="playback_node",
             output="screen", parameters=[str(config_dir / "playback_node.yaml")]),
        Node(package="vr_asr", executable="asr_node", name="asr_node",
             output="screen", parameters=[str(config_dir / "asr_node.yaml")]),
        Node(package="vr_tts", executable="tts_node", name="tts_node",
             output="screen", parameters=[str(config_dir / "tts_node.yaml")]),
        Node(package="vr_llm", executable="fast_llm_node", name="fast_llm_node",
             output="screen", parameters=[str(config_dir / "llm_nodes.yaml")]),
        Node(package="vr_llm", executable="reasoning_llm_node", name="reasoning_llm_node",
             output="screen", parameters=[str(config_dir / "llm_nodes.yaml")]),
        Node(package="vr_brain", executable="brain_node", name="brain_node", output="screen"),
    ])

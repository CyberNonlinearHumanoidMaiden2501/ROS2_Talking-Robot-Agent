from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default_config = str(Path(__file__).resolve().parents[3] / "config")
    config_arg = DeclareLaunchArgument("config_dir", default_value=default_config)
    config_dir = LaunchConfiguration("config_dir")
    params = [{"config_dir": config_dir}]

    return LaunchDescription([
        config_arg,
        Node(package="vr_audio", executable="audio_node", name="audio_node",
             output="screen", parameters=params),
        Node(package="vr_asr", executable="asr_node", name="asr_node",
             output="screen", parameters=params),
        Node(package="vr_tts", executable="tts_node", name="tts_node",
             output="screen", parameters=params),
        Node(package="vr_llm", executable="fast_llm_node", name="fast_llm_node", output="screen"),
        Node(package="vr_llm", executable="reasoning_llm_node", name="reasoning_llm_node", output="screen"),
        Node(package="vr_brain", executable="brain_node", name="brain_node", output="screen"),
    ])

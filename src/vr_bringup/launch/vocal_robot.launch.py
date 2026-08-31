from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package="vr_audio", executable="audio_node", name="audio_node", output="screen"),
        Node(package="vr_asr", executable="asr_node", name="asr_node", output="screen"),
        Node(package="vr_tts", executable="tts_node", name="tts_node", output="screen"),
        Node(package="vr_llm", executable="fast_llm_node", name="fast_llm_node", output="screen"),
        Node(package="vr_llm", executable="reasoning_llm_node", name="reasoning_llm_node", output="screen"),
        Node(package="vr_brain", executable="brain_node", name="brain_node", output="screen"),
    ])

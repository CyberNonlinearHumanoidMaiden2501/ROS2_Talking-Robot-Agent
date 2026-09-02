#!/usr/bin/env python3
"""Say a sentence through the vocal-robot stack (TTS -> audio Play action).

Usage:
    python scripts/say.py "Hello, I am your assistant."
    python scripts/say.py "你好，今天过得怎么样？"          # CJK text auto-picks the zh voice
    python scripts/say.py "Hi there" --voice af_bella --speed 1.1
"""

import argparse
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from vr_interfaces.action import Play
from vr_interfaces.msg import SpeechSegment
from vr_interfaces.srv import Synthesize


def is_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def main():
    parser = argparse.ArgumentParser(description="Say a sentence via TTS + audio playback")
    parser.add_argument("text")
    parser.add_argument("--voice", default="", help="kokoro voice id (default: af_heart / zf_xiaobei)")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    rclpy.init()
    node = Node("say_cli")
    synth_cli = node.create_client(Synthesize, "tts/synthesize")
    play_cli = ActionClient(node, Play, "audio/play")

    if not synth_cli.wait_for_service(timeout_sec=10.0) or not play_cli.wait_for_server(timeout_sec=10.0):
        node.get_logger().error("tts/synthesize or audio/play service not available; is the stack running?")
        return 1

    voice = args.voice or ("zf_001" if is_cjk(args.text) else "")
    req = Synthesize.Request()
    req.text = args.text
    req.voice = voice
    req.speed = float(args.speed)
    node.get_logger().info(f"synthesizing with voice={voice or 'default'!r}...")
    future = synth_cli.call_async(req)
    rclpy.spin_until_future_complete(node, future)
    resp = future.result()
    if not resp.success:
        node.get_logger().error(f"synthesis failed: {resp.error}")
        return 1

    goal = Play.Goal()
    goal.segments = [SpeechSegment(samples=resp.samples)]
    goal.sample_rate = resp.sample_rate
    node.get_logger().info(f"playing {len(resp.samples) / resp.sample_rate:.1f}s of audio...")
    goal_future = play_cli.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, goal_future)
    goal_handle = goal_future.result()
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result().result
    if result.completed:
        node.get_logger().info("done")
    else:
        node.get_logger().warn(f"interrupted: segment {result.last_segment_index}, "
                               f"{result.samples_played_in_last} samples played")

    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())

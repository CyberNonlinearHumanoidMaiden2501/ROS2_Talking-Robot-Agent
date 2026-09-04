"""Dev test (software-only, mock audio): cancel a Play goal mid-playback and
verify the truncation result.

Requires the stack to be running with mock audio
(VOCAL_ROBOT_MOCK_AUDIO=1). Mock playback is timer-paced, so timing behaves
like real playback without any speaker.
"""

import sys
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from vr_interfaces.action import Play
from vr_interfaces.msg import SpeechSegment


def main():
    rclpy.init()
    node = Node("play_cancel_cli")
    cli = ActionClient(node, Play, "audio/play")
    if not cli.wait_for_server(timeout_sec=10.0):
        print("audio/play not available; is the stack running?")
        return 1

    # ~5 s of silent audio at 24 kHz
    goal = Play.Goal()
    goal.segments = [SpeechSegment(samples=[0] * (24000 * 5))]
    goal.sample_rate = 24000

    future = cli.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future)
    handle = future.result()
    if not handle.accepted:
        print("goal rejected unexpectedly")
        return 1

    time.sleep(0.5)   # let ~0.5 s play, then interrupt
    cancel_future = handle.cancel_goal_async()
    rclpy.spin_until_future_complete(node, cancel_future)
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=10.0)
    res = result_future.result().result

    # play ~0.5 s at tick pace; bound generously at 1.5 s worth of samples
    ok = (not res.completed
          and res.last_segment_index == 0
          and res.samples_played_in_last < 24000 * 1.5)
    print(f"[cancel] {'PASS' if ok else 'FAIL'}  completed={res.completed} "
          f"last_segment={res.last_segment_index} "
          f"samples_in_last={res.samples_played_in_last} "
          f"(~{res.samples_played_in_last / 24000:.2f}s)")

    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

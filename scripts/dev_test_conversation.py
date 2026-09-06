"""Dev test (software-only, mock stack + real DeepSeek API): full conversation
loop and barge-in through the running stack.

Phase 1: publish a synthesized instruction through /audio/raw; expect the
brain to generate and play a reply containing the instructed text.
Phase 2: publish a long-question; while the reply is playing, publish a short
interjection; expect playback to be cut short (barge-in) and a second reply
to be generated for the interjection.

Requires the stack running with mock audio (capture silent) and network
access for the DeepSeek API.
"""

import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from scipy.signal import resample_poly
from std_msgs.msg import Bool, String

from vr_interfaces.msg import AudioChunk

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "vr_tts"))

from vr_tts.kokoro_engine import KokoroEngine  # noqa: E402

BLOCK = 512


def synth_16k(engine, text):
    samples, rate = engine.synth(text, "af_heart")
    audio16 = resample_poly(samples.astype(np.float32), 2, 3) / 32768.0
    return (np.clip(audio16, -1, 1) * 32767).astype(np.int16)


class ConvCli(Node):
    def __init__(self):
        super().__init__("conv_cli")
        self.raw_pub = self.create_publisher(AudioChunk, "audio/raw", 10)
        self.brain_logs = []
        self.playing = False
        self.create_subscription(String, "brain/log", lambda m: self.brain_logs.append(m.data), 10)
        self.create_subscription(Bool, "audio/playing", lambda m: setattr(self, "playing", m.data), 10)

    def speak(self, pcm, pace=0.03):
        def pb(a):
            m = AudioChunk()
            m.header.stamp = self.get_clock().now().to_msg()
            m.samples = a.tolist()
            self.raw_pub.publish(m)

        n = len(pcm) // BLOCK * BLOCK
        for i in range(0, n, BLOCK):
            pb(pcm[i:i + BLOCK])
            time.sleep(pace)
        for _ in range(int(0.8 * 16000 / BLOCK)):
            pb(np.zeros(BLOCK, dtype=np.int16))
            time.sleep(pace)

    def wait_for(self, pred, timeout, what):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if pred():
                return True
            rclpy.spin_once(self, timeout_sec=0.1)
        print(f"  TIMEOUT waiting for {what}")
        return False

    def log_count(self, prefix):
        return sum(1 for l in self.brain_logs if l.startswith(prefix))


def main():
    rclpy.init()
    node = ConvCli()
    engine = KokoroEngine(device=None)
    ok = True

    time.sleep(3.0)   # DDS discovery for the whole stack

    # ---- Phase 1: fixed instruction ----
    node.speak(synth_16k(engine, "Reply with exactly the words hello human."))
    reply_seen = node.wait_for(
        lambda: any("hello human" in l.lower() for l in node.brain_logs), 90, "phase1 reply")
    ok &= reply_seen
    print(f"[phase1 reply] {'PASS' if reply_seen else 'FAIL'}")
    node.wait_for(lambda: node.playing, 60, "phase1 playback start")
    node.wait_for(lambda: not node.playing, 60, "phase1 speech end")
    print(f"[phase1 speech] {'PASS' if not node.playing else 'FAIL'}")

    # ---- Phase 2: barge-in ----
    replies_before = node.log_count("reply:")
    node.speak(synth_16k(engine, "Tell me a long story about a robot who learned to paint."))
    started = node.wait_for(lambda: node.playing, 90, "story playback start")
    ok &= started
    time.sleep(1.5)   # let the story play, then interrupt
    node.speak(synth_16k(engine, "Stop."))

    interrupted = node.wait_for(
        lambda: any("interrupted" in l for l in node.brain_logs), 60, "interrupt log")
    ok &= interrupted
    print(f"[phase2 interrupt] {'PASS' if interrupted else 'FAIL'}")

    second_reply = node.wait_for(
        lambda: node.log_count("reply:") > replies_before + 1, 90, "second reply after interrupt")
    ok &= second_reply
    print(f"[phase2 second reply] {'PASS' if second_reply else 'FAIL'}")

    print("CONVERSATION", "PASS" if ok else "FAIL")
    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

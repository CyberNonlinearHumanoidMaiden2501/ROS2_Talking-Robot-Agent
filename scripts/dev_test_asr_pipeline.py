"""Dev test (software-only, mock stack): feed a synthesized sentence through
the vad_node -> asr_node chain on topics and verify the transcription.

Requires the stack running with mock audio (capture is silent, so
/audio/raw is free for this publisher). Segmentation is sample-count based,
so blocks may be published as fast as the executor handles them.
"""

import difflib
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from scipy.signal import resample_poly

from vr_interfaces.msg import AudioChunk, Utterance

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "vr_tts"))

from vr_tts.kokoro_engine import KokoroEngine  # noqa: E402

TEXT = "The pipeline is working end to end."
BLOCK = 512


def main():
    engine = KokoroEngine(device=None)
    samples, rate = engine.synth(TEXT, "af_heart")
    audio16 = resample_poly(samples.astype(np.float32), 2, 3) / 32768.0  # 24k int16 -> 16k float
    pcm = (np.clip(audio16, -1.0, 1.0) * 32767.0).astype(np.int16)

    rclpy.init()
    node = Node("pipeline_cli")
    raw_pub = node.create_publisher(AudioChunk, "audio/raw", 10)
    received = []

    def on_utterance(msg):
        received.append(msg)

    node.create_subscription(Utterance, "asr/utterance", on_utterance, 10)

    # wait for DDS discovery so vad_node/asr_node are connected before we publish
    time.sleep(3.0)
    print("publishing synthesized speech + trailing silence ...")

    def publish_block(samples):
        msg = AudioChunk()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.samples = samples.tolist()
        raw_pub.publish(msg)

    n = len(pcm) // BLOCK * BLOCK
    # pace at the real capture cadence (~32 ms): bursting would overflow the
    # DDS writer's KEEP_LAST-10 history and silently drop most blocks
    for i in range(0, n, BLOCK):
        publish_block(pcm[i:i + BLOCK])
        time.sleep(0.03)
    # trailing silence so the segmenter's end-of-speech condition triggers
    for _ in range(int(0.8 * 16000 / BLOCK)):
        publish_block(np.zeros(BLOCK, dtype=np.int16))
        time.sleep(0.03)
    print(f"published {n // BLOCK} speech blocks ({n / 16000:.1f}s), waiting for transcription...")

    deadline = time.time() + 20.0
    while not received and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)

    if not received:
        print("[pipeline] FAIL  no utterance received within 20s")
        node.destroy_node()
        rclpy.shutdown()
        return 1

    got = received[0].text
    ratio = difflib.SequenceMatcher(None, got.lower().strip(), TEXT.lower().strip()).ratio()
    ok = ratio > 0.7
    print(f"[pipeline] {'PASS' if ok else 'FAIL'}  ratio={ratio:.2f}  lang={received[0].language}")
    print(f"           expected: {TEXT}")
    print(f"           heard   : {got}")

    node.destroy_node()
    rclpy.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

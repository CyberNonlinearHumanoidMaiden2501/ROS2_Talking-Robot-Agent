"""Dev test (software-only): PlayTracker truncation/feedback math."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "vr_audio"))
from vr_audio.playback import PlayTracker  # noqa: E402


def main():
    ok = True

    # partial play then interrupt
    t = PlayTracker([4800, 2400, 1200])
    t.advance(5000)
    passed = t.feedback() == (1, 200) and t.result() == (False, 1, 200)
    ok &= passed
    print(f"[interrupt] {'PASS' if passed else 'FAIL'}  feedback={t.feedback()} result={t.result()}")

    # finish from there
    t.advance(3400)
    passed = t.done and t.result() == (True, 2, 1200)
    ok &= passed
    print(f"[complete] {'PASS' if passed else 'FAIL'}  result={t.result()}")

    # empty goal
    t2 = PlayTracker([])
    passed = t2.done and t2.result() == (True, -1, 0)
    ok &= passed
    print(f"[empty] {'PASS' if passed else 'FAIL'}  result={t2.result()}")

    # exact segment boundary advance
    t3 = PlayTracker([512, 512])
    t3.advance(512)
    passed = t3.feedback() == (1, 0)
    ok &= passed
    print(f"[boundary] {'PASS' if passed else 'FAIL'}  feedback={t3.feedback()}")

    print("PLAYBACK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

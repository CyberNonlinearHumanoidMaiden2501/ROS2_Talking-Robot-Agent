"""Dev test (software-only): brain utility functions — sentence splitting,
as-spoken truncation mapping, conversation store, CJK detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "vr_brain"))

from vr_brain.conversation import (ConversationStore, as_spoken_text,  # noqa: E402
                                   is_cjk, split_sentences)


def main():
    ok = True

    parts = split_sentences("Hello! How are you? I'm fine.")
    ok &= parts == ["Hello!", "How are you?", "I'm fine."]
    print(f"[split] {'PASS' if ok else 'FAIL'}  {parts}")

    texts = ["AAA", "BBB", "CCC"]
    counts = [3, 3, 3]

    spoken, interrupted = as_spoken_text(texts, counts, True, 2, 3)
    ok &= spoken == "AAA BBB CCC" and not interrupted
    print(f"[completed] {'PASS' if spoken == 'AAA BBB CCC' and not interrupted else 'FAIL'}  {spoken!r}")

    spoken, interrupted = as_spoken_text(texts, counts, False, 1, 2)
    ok &= spoken == "AAA BB" and interrupted
    print(f"[mid-segment] {'PASS' if spoken == 'AAA BB' and interrupted else 'FAIL'}  {spoken!r}")

    spoken, interrupted = as_spoken_text(texts, counts, False, 0, 0)
    ok &= spoken == "" and interrupted
    print(f"[no-audio] {'PASS' if spoken == '' and interrupted else 'FAIL'}  {spoken!r}")

    store = ConversationStore(limit=3)
    for i in range(5):
        store.add("user", f"m{i}")
    msgs = store.messages_for_llm()
    ok &= [m["content"] for m in msgs] == ["m2", "m3", "m4"]
    print(f"[store] {'PASS' if [m['content'] for m in msgs] == ['m2', 'm3', 'm4'] else 'FAIL'}  "
          f"{[m['content'] for m in msgs]}")

    ok &= is_cjk("你好 world") and not is_cjk("hello")
    print(f"[cjk] {'PASS' if ok else 'FAIL'}")

    print("BRAIN_UTILS", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

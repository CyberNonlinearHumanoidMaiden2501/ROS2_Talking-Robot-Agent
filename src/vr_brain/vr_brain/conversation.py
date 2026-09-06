"""Conversation store and as-spoken truncation mapping (pure, file-testable)."""

from __future__ import annotations

import re


def split_sentences(text: str) -> list[str]:
    """Split reply text into speakable sentence chunks."""
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?.])\s*|\n+", text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def is_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def as_spoken_text(segment_texts, segment_sample_counts,
                   completed, last_index, samples_in_last):
    """Map a Play result to the text the user actually heard.

    Returns (spoken_text, interrupted). For a completed goal the full text is
    returned with interrupted=False; for a truncated goal the finished
    segments plus the proportional part of the last one, with interrupted=True.
    """
    if completed or last_index >= len(segment_texts):
        return " ".join(segment_texts), False
    if last_index <= 0 and samples_in_last <= 0:
        return "", True
    full = segment_texts[last_index]
    frac = min(samples_in_last / segment_sample_counts[last_index], 1.0)
    partial = full[: max(1, int(len(full) * frac))]
    return " ".join(segment_texts[:last_index] + [partial]), True


class ConversationStore:
    """Canonical conversation history (the brain is its only owner)."""

    def __init__(self, limit: int = 20):
        self._messages = []
        self._limit = limit

    def add(self, role: str, text: str):
        self._messages.append({"role": role, "content": text})
        if len(self._messages) > self._limit:
            self._messages = self._messages[-self._limit:]

    def messages_for_llm(self) -> list[dict]:
        return [{"role": m["role"], "content": m["content"]} for m in self._messages]

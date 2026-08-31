"""Pure playback bookkeeping for the Play action — no hardware (unit-testable)."""

from __future__ import annotations


class PlayTracker:
    """Tracks exactly how far playback got, so an interrupt can be reported
    as (last_segment_index, samples_played_in_last) — the truncation point
    the brain uses to record a response "as spoken"."""

    def __init__(self, segment_lengths):
        self.segment_lengths = list(segment_lengths)
        self.segment_index = 0
        self.samples_in_segment = 0

    @property
    def done(self) -> bool:
        return self.segment_index >= len(self.segment_lengths)

    def advance(self, samples: int):
        """Account for `samples` more samples played."""
        while samples > 0 and not self.done:
            remaining = self.segment_lengths[self.segment_index] - self.samples_in_segment
            if samples < remaining:
                self.samples_in_segment += samples
                samples = 0
            else:
                samples -= remaining
                self.segment_index += 1
                self.samples_in_segment = 0

    def feedback(self) -> tuple[int, int]:
        """(segment_index, samples_played) — Play.feedback values."""
        if self.done:
            last = len(self.segment_lengths) - 1
            return last, self.segment_lengths[last] if self.segment_lengths else 0
        return self.segment_index, self.samples_in_segment

    def result(self) -> tuple[bool, int, int]:
        """(completed, last_segment_index, samples_played_in_last) — Play.result values."""
        if self.done:
            last = len(self.segment_lengths) - 1
            return True, last, self.segment_lengths[last] if self.segment_lengths else 0
        return False, self.segment_index, self.samples_in_segment

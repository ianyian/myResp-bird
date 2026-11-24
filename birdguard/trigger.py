"""Decide *when* to react: confirmation, cooldown and active hours.

Kept free of hardware and real clocks so it can be unit-tested exactly.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, time


class TriggerPolicy:
    """Confirms a bird over several frames and enforces the cooldown.

    The cooldown is measured from the moment a trigger fires (= the sound
    starts), so with a 10 s sound and a 30 s cooldown there are 20 s of
    silence before the next possible trigger.
    """

    def __init__(self, confirm_frames: int, window_frames: int, cooldown_seconds: float):
        self.confirm_frames = confirm_frames
        self.cooldown_seconds = cooldown_seconds
        self._history: deque[bool] = deque(maxlen=window_frames)
        self.last_trigger: float | None = None

    def observe(self, bird_seen: bool) -> bool:
        """Record one frame. Returns True when a bird is *confirmed*."""
        self._history.append(bird_seen)
        return sum(self._history) >= self.confirm_frames

    def cooldown_remaining(self, now: float) -> float:
        if self.last_trigger is None:
            return 0.0
        return max(0.0, self.cooldown_seconds - (now - self.last_trigger))

    def in_cooldown(self, now: float) -> bool:
        return self.cooldown_remaining(now) > 0

    def mark_triggered(self, now: float) -> None:
        self.last_trigger = now
        self._history.clear()


def parse_hhmm(value: str) -> time:
    hh, mm = str(value).strip().split(":")
    return time(int(hh), int(mm))


class Schedule:
    """Active window, e.g. 07:00-18:00. Start is inclusive, end exclusive.

    Windows that cross midnight (e.g. 22:00-06:00) also work.
    """

    def __init__(self, start: str, end: str, enabled: bool = True):
        self.enabled = enabled
        self.start = parse_hhmm(start)
        self.end = parse_hhmm(end)

    def is_active(self, now: datetime) -> bool:
        if not self.enabled:
            return True
        t = now.time()
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end

    def describe(self) -> str:
        if not self.enabled:
            return "always active"
        return f"{self.start:%H:%M}-{self.end:%H:%M}"

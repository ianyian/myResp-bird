"""Stand-in used when the camera or AI HAT can't be opened.

Instead of crashing (which also takes the web page down), BirdGuard keeps
running, shows the problem on the dashboard and live view, and retries
opening the real detector every `retry_seconds`.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .base import Detection, Detector

log = logging.getLogger(__name__)


class UnavailableDetector(Detector):
    def __init__(self, error: str, factory: Callable[[], Detector], retry_seconds: float = 30,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.error = error
        self.factory = factory
        self.retry_seconds = retry_seconds
        self.clock, self.sleep = clock, sleep
        self.inner: Detector | None = None
        self._next_try = clock() + retry_seconds

    @property
    def can_simulate(self) -> bool:  # type: ignore[override]
        return bool(self.inner and self.inner.can_simulate)

    def inject_bird(self, *a, **k):
        return self.inner.inject_bird(*a, **k)  # only reachable when can_simulate

    def read(self) -> tuple[np.ndarray, list[Detection]]:
        if self.inner is None and self.clock() >= self._next_try:
            self._next_try = self.clock() + self.retry_seconds
            try:
                self.inner = self.factory()
                self.error = ""
                log.info("camera / AI HAT is working now")
            except Exception as exc:
                self.error = describe_error(exc)
                log.warning("still can't open camera / AI HAT: %s", self.error)
        if self.inner is not None:
            return self.inner.read()
        self.sleep(1.0)
        return self._error_frame(), []

    def _error_frame(self) -> np.ndarray:
        img = Image.new("RGB", (960, 720), (40, 20, 20))
        d = ImageDraw.Draw(img)
        try:
            big, small = ImageFont.load_default(size=34), ImageFont.load_default(size=22)
        except TypeError:
            big = small = ImageFont.load_default()
        d.text((30, 40), "Camera / AI HAT not available", font=big, fill=(255, 120, 120))
        y = 110
        for line in _wrap(self.error, 70):
            d.text((30, y), line, font=small, fill=(255, 255, 255)); y += 32
        d.text((30, y + 30), f"Retrying every {self.retry_seconds:.0f} s.  Run: python3 -m birdguard check",
               font=small, fill=(200, 200, 200))
        return np.asarray(img)

    def close(self) -> None:
        if self.inner is not None:
            self.inner.close()


def describe_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    if "OUT_OF_PHYSICAL_DEVICES" in text or "HAILO_OUT_OF_PHYSICAL" in text:
        text += (" -- the AI HAT driver is not loaded (often after a kernel update) or another "
                 "program is using it. See README > Troubleshooting.")
    return text


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + ([cur] if cur else [])

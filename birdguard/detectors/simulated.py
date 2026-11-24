"""A fake camera for testing without hardware.

Draws a sky scene; when a bird is "injected" (web button, or randomly),
a cartoon bird flies across and is reported as a detection.
"""

from __future__ import annotations

import random
import threading
import time

import numpy as np
from PIL import Image, ImageDraw

from .base import Detection, Detector


class SimulatedDetector(Detector):
    can_simulate = True

    def __init__(self, cfg):
        sim = cfg.get("simulation", {})
        self.w, self.h = 960, 720
        self.fps = 10
        self.visible = float(sim.get("bird_visible_seconds", 3))
        self.random_every = float(sim.get("random_bird_every_seconds", 0))
        self.score = 0.85
        self._bird_until = 0.0
        self._bird_start = 0.0
        self._y = 0.3
        self._lock = threading.Lock()
        self._next_frame = time.monotonic()
        self._background = self._make_background()

    def _make_background(self) -> np.ndarray:
        sky = np.linspace([120, 170, 230], [200, 225, 245], self.h).astype(np.uint8)
        img = np.repeat(sky[:, None, :], self.w, axis=1)
        img[int(self.h * 0.8):] = (90, 140, 70)  # grass
        img[int(self.h * 0.55):int(self.h * 0.8), int(self.w * 0.1):int(self.w * 0.45)] = (150, 110, 90)  # fence/roof
        return img

    def inject_bird(self, seconds: float | None = None) -> None:
        with self._lock:
            now = time.monotonic()
            self._bird_start = now
            self._bird_until = now + (seconds or self.visible)
            self._y = random.uniform(0.15, 0.6)

    def read(self) -> tuple[np.ndarray, list[Detection]]:
        # pace like a real camera
        self._next_frame += 1 / self.fps
        delay = self._next_frame - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            self._next_frame = time.monotonic()

        now = time.monotonic()
        if self.random_every > 0 and now > self._bird_until:
            if random.random() < 1 / (self.random_every * self.fps):
                self.inject_bird()

        img = Image.fromarray(self._background.copy())
        dets: list[Detection] = []
        with self._lock:
            if now < self._bird_until:
                progress = (now - self._bird_start) / max(0.1, self._bird_until - self._bird_start)
                cx, cy = 0.1 + 0.8 * progress, self._y
                bw, bh = 0.12, 0.08
                box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
                self._draw_bird(img, box, now)
                dets.append(Detection("bird", self.score, box))
        return np.asarray(img), dets

    def _draw_bird(self, img: Image.Image, box, now: float) -> None:
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = box[0] * self.w, box[1] * self.h, box[2] * self.w, box[3] * self.h
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        flap = 15 if int(now * 6) % 2 else -15
        d.ellipse([cx - 25, cy - 12, cx + 25, cy + 12], fill=(60, 50, 40))
        d.ellipse([cx + 18, cy - 18, cx + 38, cy + 2], fill=(60, 50, 40))
        d.polygon([(cx + 38, cy - 9), (cx + 50, cy - 6), (cx + 38, cy - 3)], fill=(240, 180, 40))
        d.polygon([(cx - 10, cy), (cx + 10, cy), (cx - 5, cy - 30 - flap)], fill=(80, 65, 50))

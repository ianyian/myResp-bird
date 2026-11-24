"""The main engine: camera -> detection -> decision -> deterrents."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

import numpy as np

from .annotate import annotate, to_jpeg
from .config import Config
from .deterrents import Deterrent
from .detectors import Detection, Detector
from .events import EventLog
from .notify import NtfyNotifier
from .trigger import Schedule, TriggerPolicy

log = logging.getLogger(__name__)


class BirdGuard:
    def __init__(
        self,
        cfg: Config,
        detector: Detector,
        deterrents: list[Deterrent],
        notifier: NtfyNotifier | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = datetime.now,
    ):
        self.cfg = cfg
        self.detector = detector
        self.deterrents = deterrents
        self.notifier = notifier or NtfyNotifier({})
        self.clock = clock
        self.wall_clock = wall_clock

        d, t, s = cfg["detector"], cfg["trigger"], cfg["schedule"]
        self.targets = set(d.get("target_labels", ["bird"]))
        self.threshold = float(d.get("score_threshold", 0.45))
        self.policy = TriggerPolicy(t["confirm_frames"], t["window_frames"], t["cooldown_seconds"])
        self.schedule = Schedule(s["start"], s["end"], s.get("enabled", True))
        self.events = EventLog(cfg.path(cfg["storage"]["data_dir"]), cfg["storage"].get("keep_events", 500))

        web = cfg.get("web", {})
        self.stream_width = int(web.get("stream_width", 640))
        self.stream_interval = 1.0 / max(1, float(web.get("stream_fps", 5)))

        self.enabled = True
        self.ignore_schedule = False
        self.running = False
        self.latest_jpeg: bytes | None = None
        self.frame_seq = 0
        self.fps = 0.0
        self.last_bird_seen: str | None = None
        self.last_error: str | None = None
        self._last_stream_encode = 0.0
        self._last_quiet_event: float | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ loop

    def run_forever(self) -> None:
        self.running = True
        log.info("BirdGuard running - active hours %s, cooldown %ss",
                 self.schedule.describe(), self.policy.cooldown_seconds)
        frames, t0 = 0, time.monotonic()
        errors = 0
        while self.running:
            try:
                frame, dets = self.detector.read()
                errors = 0
            except Exception as exc:
                errors += 1
                self.last_error = f"camera/detector error: {exc}"
                log.exception("detector read failed")
                if errors >= 20:
                    raise  # let systemd restart the whole program
                time.sleep(1)
                continue
            self.process(frame, dets)
            frames += 1
            if time.monotonic() - t0 >= 5:
                self.fps = frames / (time.monotonic() - t0)
                frames, t0 = 0, time.monotonic()

    def stop(self) -> None:
        self.running = False

    # --------------------------------------------------------------- decision

    def is_active_hours(self, when: datetime | None = None) -> bool:
        return self.ignore_schedule or self.schedule.is_active(when or self.wall_clock())

    def process(self, frame: np.ndarray, dets: list[Detection]) -> str | None:
        """Handle one frame. Returns 'triggered', 'quiet', or None."""
        now, when = self.clock(), self.wall_clock()
        birds = [x for x in dets if x.label in self.targets and x.score >= self.threshold]
        confirmed = self.policy.observe(bool(birds))
        if birds:
            self.last_bird_seen = when.isoformat(timespec="seconds")

        outcome = None
        img = None
        if confirmed and self.enabled and not self.policy.in_cooldown(now):
            img = annotate(frame, dets, self.targets, self.threshold, self._status(when, now))
            best = max(x.score for x in birds) if birds else 0.0
            if self.is_active_hours(when):
                self._trigger(now, when, img, best)
                outcome = "triggered"
            elif self._last_quiet_event is None or now - self._last_quiet_event >= self.policy.cooldown_seconds:
                # Seen during quiet hours: log it (rate-limited), but stay silent.
                self._last_quiet_event = now
                jpeg = to_jpeg(img)
                self.events.add("quiet_hours", when, jpeg, score=round(best, 2))
                if self.notifier.notify_quiet:
                    self.notifier.notify("Bird seen (quiet hours)", f"No sound played. {best:.0%}", jpeg)
                outcome = "quiet"

        self._update_stream(frame, dets, when, now, img)
        return outcome

    def _trigger(self, now: float, when: datetime, img, score: float) -> None:
        self.policy.mark_triggered(now)  # cooldown starts when the sound starts
        actions = self._activate_all()
        jpeg = to_jpeg(img)
        event = self.events.add("triggered", when, jpeg, score=round(score, 2), **actions)
        log.info("BIRD! score %.2f -> %s", score, actions)
        sounds = ", ".join(actions.get("sound", [])) or "deterrents"
        self.notifier.notify("Bird chased away", f"{when:%H:%M:%S} - played {sounds} ({score:.0%})", jpeg)
        return event

    def _activate_all(self) -> dict:
        actions: dict = {}
        for det in self.deterrents:
            try:
                actions.update(det.activate())
            except Exception as exc:
                log.exception("deterrent %s failed", det.name)
                actions[f"{det.name}_error"] = str(exc)
        return actions

    def test_deterrents(self) -> dict:
        """Manual test from the web page. Never overlaps a running sound."""
        if any(d.is_active() for d in self.deterrents):
            return {"ok": False, "reason": "a sound is already playing"}
        self.policy.mark_triggered(self.clock())  # counts as a trigger for the cooldown
        actions = self._activate_all()
        self.events.add("test", self.wall_clock(), None, **actions)
        return {"ok": True, **actions}

    # ----------------------------------------------------------------- stream

    def _status(self, when: datetime, now: float) -> str:
        state = "ACTIVE" if self.is_active_hours(when) else "QUIET HOURS"
        if not self.enabled:
            state = "PAUSED"
        cd = self.policy.cooldown_remaining(now)
        return f"{when:%H:%M:%S}  {state}" + (f"  cooldown {cd:.0f}s" if cd else "")

    def _update_stream(self, frame, dets, when, now, img) -> None:
        if now - self._last_stream_encode < self.stream_interval:
            return
        self._last_stream_encode = now
        if img is None:
            img = annotate(frame, dets, self.targets, self.threshold, self._status(when, now))
        jpeg = to_jpeg(img, self.stream_width, quality=70)
        with self._lock:
            self.latest_jpeg = jpeg
            self.frame_seq += 1

    def status(self) -> dict:
        now, when = self.clock(), self.wall_clock()
        return {
            "time": when.isoformat(timespec="seconds"),
            "enabled": self.enabled,
            "active_hours": self.is_active_hours(when),
            "schedule": self.schedule.describe(),
            "ignore_schedule": self.ignore_schedule,
            "cooldown_remaining": round(self.policy.cooldown_remaining(now), 1),
            "playing": any(d.is_active() for d in self.deterrents),
            "triggers_today": self.events.count_today("triggered", when),
            "last_bird_seen": self.last_bird_seen,
            "fps": round(self.fps, 1),
            "backend": self.cfg["detector"]["backend"],
            "can_simulate": self.detector.can_simulate,
            "deterrents": [d.name for d in self.deterrents],
            "notifications": self.notifier.enabled,
            "last_error": self.last_error,
        }

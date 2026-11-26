"""Tests for the core rules, using a fake clock so they run instantly.

Run with:  python -m pytest
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from birdguard.app import BirdGuard
from birdguard.config import load_config
from birdguard.deterrents.base import Deterrent
from birdguard.detectors.base import Detection, Detector
from birdguard.sounds import GENERATORS, SoundComposer
from birdguard.trigger import Schedule, TriggerPolicy

ROOT = Path(__file__).resolve().parent.parent
BIRD = [Detection("bird", 0.9, (0.4, 0.4, 0.6, 0.6))]
FRAME = np.zeros((120, 160, 3), dtype=np.uint8)


# --------------------------------------------------------------- policy

def confirm(policy: TriggerPolicy, frames: int = 3) -> bool:
    return any([policy.observe(True) for _ in range(frames)])


def test_needs_several_frames_to_confirm():
    p = TriggerPolicy(confirm_frames=3, window_frames=5, cooldown_seconds=30)
    assert not p.observe(True)
    assert not p.observe(False)
    assert not p.observe(True)
    assert p.observe(True)  # 3 of the last 5


def test_single_glitch_frames_never_confirm():
    p = TriggerPolicy(3, 5, 30)
    for _ in range(50):
        assert not p.observe(True)
        for _ in range(4):
            assert not p.observe(False)


def test_cooldown_counts_from_trigger_start():
    p = TriggerPolicy(3, 5, 30)
    p.mark_triggered(100.0)
    assert p.in_cooldown(100.0)
    assert p.in_cooldown(110.0)    # sound just finished (10 s) - still locked
    assert p.in_cooldown(129.9)
    assert not p.in_cooldown(130.0)
    assert p.cooldown_remaining(120.0) == pytest.approx(10.0)


# ------------------------------------------------------------- schedule

@pytest.mark.parametrize("hhmm,active", [
    ("06:59", False), ("07:00", True), ("12:00", True), ("17:59", True), ("18:00", False), ("23:00", False),
])
def test_schedule_7am_to_6pm(hhmm, active):
    s = Schedule("07:00", "18:00")
    h, m = map(int, hhmm.split(":"))
    assert s.is_active(datetime(2026, 6, 1, h, m)) is active


def test_schedule_over_midnight():
    s = Schedule("22:00", "06:00")
    assert s.is_active(datetime(2026, 6, 1, 23, 0))
    assert s.is_active(datetime(2026, 6, 1, 3, 0))
    assert not s.is_active(datetime(2026, 6, 1, 12, 0))


# --------------------------------------------------------------- sounds

def test_every_sound_kind_generates_audio():
    rng = np.random.default_rng(1)
    for name, gen in GENERATORS.items():
        x = gen(rng, 22050)
        assert len(x) > 0 and np.isfinite(x).all(), name


def test_composed_sound_is_exactly_10_seconds_and_varies():
    c = SoundComposer(duration=10, sample_rate=22050, seed=42)
    a, kinds_a = c.compose()
    b, kinds_b = c.compose()
    assert len(a) == len(b) == 10 * 22050
    assert np.max(np.abs(a)) <= 1.0
    assert not np.array_equal(a, b)
    for kinds in (kinds_a, kinds_b):
        assert all(x != y for x, y in zip(kinds, kinds[1:])), "same kind twice in a row"


def test_wav_library_is_used(tmp_path):
    from birdguard.sounds import write_wav
    write_wav(tmp_path / "hawk.wav", np.sin(np.linspace(0, 2000, 22050)).astype(np.float32), 22050)
    c = SoundComposer(duration=5, sample_rate=22050, use_generated=False, library_dir=tmp_path, seed=1)
    _, kinds = c.compose()
    assert set(kinds) == {"file:hawk"}


# ------------------------------------------------------ whole pipeline

class FakeDeterrent(Deterrent):
    name = "fake"

    def __init__(self):
        self.activations = 0

    def activate(self):
        self.activations += 1
        return {"sound": ["fake"]}


class FakeDetector(Detector):
    def read(self):
        raise NotImplementedError


class Clock:
    def __init__(self, hour=12):
        self.t = 1000.0
        self.hour = hour

    def mono(self):
        return self.t

    def wall(self):
        return datetime(2026, 6, 1, self.hour, 0, 0) if self.hour is not None else datetime.now()


@pytest.fixture
def make_guard(tmp_path):
    def _make(hour=12):
        cfg = load_config(ROOT / "config.yaml", {"storage": {"data_dir": str(tmp_path)}})
        clock = Clock(hour)
        det = FakeDeterrent()
        guard = BirdGuard(cfg, FakeDetector(), [det], clock=clock.mono, wall_clock=clock.wall)
        return guard, det, clock
    return _make


def feed(guard, clock, seconds, fps=10, bird=True):
    outcomes = []
    for _ in range(int(seconds * fps)):
        outcomes.append(guard.process(FRAME, BIRD if bird else []))
        clock.t += 1 / fps
    return outcomes


def test_bird_staying_for_two_minutes_triggers_once_every_30s(make_guard):
    guard, det, clock = make_guard()
    feed(guard, clock, seconds=120)
    # triggers at ~0 s, 30 s, 60 s, 90 s -> exactly 4, never closer than 30 s
    assert det.activations == 4
    events = [e for e in guard.events.latest(50) if e["type"] == "triggered"]
    assert len(events) == 4 and all("snapshot" in e for e in events)


def test_no_sound_during_quiet_hours(make_guard):
    guard, det, clock = make_guard(hour=19)
    outcomes = feed(guard, clock, seconds=60)
    assert det.activations == 0
    assert outcomes.count("quiet") == 2  # logged (rate-limited) but silent


def test_paused_means_no_sound(make_guard):
    guard, det, clock = make_guard()
    guard.enabled = False
    feed(guard, clock, seconds=10)
    assert det.activations == 0


def test_test_button_respects_cooldown_rule(make_guard):
    guard, det, clock = make_guard()
    assert guard.test_deterrents()["ok"]
    feed(guard, clock, seconds=5)        # bird appears right after the test
    assert det.activations == 1          # no overlap / no second sound yet
    feed(guard, clock, seconds=30)
    assert det.activations == 2


def test_web_api(make_guard):
    from birdguard.web import create_app
    guard, det, clock = make_guard()
    client = create_app(guard).test_client()
    assert client.get("/").status_code == 200
    assert client.get("/api/status").get_json()["active_hours"] is True
    assert client.post("/api/test-sound").get_json()["ok"] is True
    assert client.post("/api/enable", json={"enabled": False}).get_json()["enabled"] is False
    assert len(client.get("/api/events").get_json()) == 1


def test_dashboard_listen_host():
    from birdguard.__main__ import listen_host
    assert listen_host("192.168.1.5") == "192.168.1.5"   # explicit setting kept
    assert listen_host("auto") in ("::", "0.0.0.0")      # dual stack when available

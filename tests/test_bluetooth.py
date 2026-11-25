"""Bluetooth speaker path, with bluetoothctl/aplay faked."""

from __future__ import annotations

import time

import pytest

from birdguard import audio


@pytest.fixture
def linux_with_aplay(monkeypatch):
    monkeypatch.setattr(audio.platform, "system", lambda: "Linux")
    monkeypatch.setattr(audio.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(audio.AudioPlayer, "_watchdog", lambda self, k: None)


def test_bluetooth_device_string(linux_with_aplay):
    p = audio.player_from_config({"bluetooth_mac": "aa:bb:cc:dd:ee:ff"})
    assert p.device == "bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp"
    assert p.command == ["aplay", "-q", "-D", "bluealsa:DEV=AA:BB:CC:DD:EE:FF,PROFILE=a2dp"]


def test_bad_mac_is_reported():
    with pytest.raises(ValueError):
        audio.Bluetooth("speaker")


def test_play_connects_first_without_blocking(linux_with_aplay, monkeypatch, tmp_path):
    calls = []

    def fake_connect(self):
        time.sleep(0.3)  # slow connection
        calls.append("connect")
        return True

    class FakeProc:
        returncode = 0
        def __init__(self, cmd, **kw):
            calls.append(cmd)
        def poll(self):
            return 0
        def communicate(self, timeout=None):
            return b"", b""

    monkeypatch.setattr(audio.Bluetooth, "ensure_connected", fake_connect)
    monkeypatch.setattr(audio.subprocess, "Popen", FakeProc)
    p = audio.player_from_config({"bluetooth_mac": "AA:BB:CC:DD:EE:FF"})
    start = time.monotonic()
    p.play(tmp_path / "x.wav")
    assert time.monotonic() - start < 0.1      # camera loop is not held up
    assert p.is_playing()                      # counts as busy while connecting
    time.sleep(0.6)
    assert calls[0] == "connect" and calls[1][-1].endswith("x.wav")
    assert not p.is_playing()


def test_no_sound_if_speaker_unreachable(linux_with_aplay, monkeypatch, tmp_path):
    monkeypatch.setattr(audio.Bluetooth, "ensure_connected", lambda self: False)
    started = []
    monkeypatch.setattr(audio.subprocess, "Popen", lambda *a, **k: started.append(a))
    p = audio.player_from_config({"bluetooth_mac": "AA:BB:CC:DD:EE:FF"})
    p.play(tmp_path / "x.wav")
    time.sleep(0.2)
    assert started == [] and not p.is_playing()


def test_usb_is_default(linux_with_aplay, monkeypatch):
    monkeypatch.setattr(audio, "find_usb_alsa_device", lambda: "plughw:CARD=Speaker,DEV=0")
    p = audio.player_from_config({})
    assert p.bluetooth is None and p.device == "plughw:CARD=Speaker,DEV=0"

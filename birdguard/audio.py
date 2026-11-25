"""Play a .wav file without blocking.

- Raspberry Pi, USB speaker:       aplay -D plughw:CARD=...
- Raspberry Pi, Bluetooth speaker: aplay -D bluealsa:DEV=<MAC>,PROFILE=a2dp
  (needs the bluez-alsa package, installed by install.sh)
- Mac:                             afplay
"""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

_CARD_RE = re.compile(r"^card (\d+): (\S+) \[(.*?)\], device (\d+): (.*)$")
_MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")


def list_alsa_devices() -> list[dict]:
    """Parse `aplay -l`. Returns [] when aplay isn't available."""
    if not shutil.which("aplay"):
        return []
    try:
        out = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return []
    devices = []
    for line in out.splitlines():
        m = _CARD_RE.match(line.strip())
        if m:
            devices.append({
                "card": int(m.group(1)), "id": m.group(2), "name": m.group(3),
                "device": int(m.group(4)), "desc": m.group(5),
            })
    return devices


def find_usb_alsa_device() -> str | None:
    for d in list_alsa_devices():
        if "usb" in (d["name"] + d["desc"] + d["id"]).lower():
            return f"plughw:CARD={d['id']},DEV={d['device']}"
    return None


class Bluetooth:
    """Keeps a paired Bluetooth speaker connected, using `bluetoothctl`."""

    def __init__(self, mac: str):
        if not _MAC_RE.match(mac):
            raise ValueError(f"bluetooth_mac '{mac}' should look like AA:BB:CC:DD:EE:FF")
        self.mac = mac.upper()
        self._lock = threading.Lock()

    def _ctl(self, *args: str, timeout: float = 20) -> str:
        try:
            return subprocess.run(
                ["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout
            ).stdout
        except Exception as exc:
            log.debug("bluetoothctl %s failed: %s", args, exc)
            return ""

    def is_connected(self) -> bool:
        return "Connected: yes" in self._ctl("info", self.mac, timeout=5)

    def ensure_connected(self) -> bool:
        with self._lock:
            if self.is_connected():
                return True
            log.info("connecting Bluetooth speaker %s ...", self.mac)
            self._ctl("connect", self.mac)
            for _ in range(10):  # the audio link needs a moment after connecting
                if self.is_connected():
                    time.sleep(1.5)
                    log.info("Bluetooth speaker connected")
                    return True
                time.sleep(0.5)
            log.warning("could not connect Bluetooth speaker %s - is it on and in Bluetooth mode?", self.mac)
            return False


class AudioPlayer:
    def __init__(self, alsa_device: str = "auto", bluetooth_mac: str = "", keepalive_seconds: float = 0):
        self._proc: subprocess.Popen | None = None
        self._pending = False
        self._lock = threading.Lock()
        self.system = platform.system()
        self.device: str | None = None
        self.bluetooth: Bluetooth | None = None

        if self.system == "Darwin" and shutil.which("afplay"):
            self.command = ["afplay"]
        elif shutil.which("aplay"):
            if bluetooth_mac:
                self.bluetooth = Bluetooth(bluetooth_mac)
                self.device = f"bluealsa:DEV={self.bluetooth.mac},PROFILE=a2dp"
            elif alsa_device == "auto":
                self.device = find_usb_alsa_device()
                if self.device is None:
                    log.warning("no USB speaker found - using the default ALSA output")
            else:
                self.device = alsa_device
            self.command = ["aplay", "-q"] + (["-D", self.device] if self.device else [])
        else:
            self.command = []
            log.warning("no audio player found (aplay/afplay) - sounds will be silent")

        if self.bluetooth:
            threading.Thread(target=self._watchdog, args=(keepalive_seconds,), daemon=True).start()

    def describe(self) -> str:
        if not self.command:
            return "none (silent)"
        return " ".join(self.command)

    # ------------------------------------------------------------ playback

    def play(self, wav: Path) -> None:
        """Start playing and return immediately."""
        self.stop()
        if not self.command:
            return
        if self.bluetooth:
            # connecting can take a few seconds - don't block the camera loop
            with self._lock:
                self._pending = True
            threading.Thread(target=self._play_bt, args=(wav,), daemon=True).start()
        else:
            self._start(wav)

    def _play_bt(self, wav: Path) -> None:
        try:
            if self.bluetooth.ensure_connected():
                self._start(wav)
        finally:
            with self._lock:
                self._pending = False

    def _start(self, wav: Path) -> None:
        try:
            proc = subprocess.Popen(
                self.command + [str(wav)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
            with self._lock:
                self._proc = proc
        except Exception as exc:
            log.error("could not start audio playback: %s", exc)

    def is_playing(self) -> bool:
        with self._lock:
            return self._pending or (self._proc is not None and self._proc.poll() is None)

    def stop(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
        try:
            _, err = proc.communicate(timeout=2)
            if proc.returncode not in (0, -15) and err:
                log.error("audio player error: %s", err.decode(errors="replace").strip())
        except Exception:
            pass

    # ------------------------------------------------- bluetooth watchdog

    def _watchdog(self, keepalive_seconds: float) -> None:
        """Reconnect the speaker if it drops, and optionally play an
        inaudible tone now and then so it doesn't switch itself off."""
        last_keepalive = time.monotonic()
        while True:
            time.sleep(60)
            if self.is_playing():
                last_keepalive = time.monotonic()
                continue
            if not self.bluetooth.ensure_connected():
                continue
            if keepalive_seconds and time.monotonic() - last_keepalive >= keepalive_seconds:
                last_keepalive = time.monotonic()
                self._keepalive()

    def _keepalive(self) -> None:
        sr = 44100
        t = np.arange(int(1.0 * sr)) / sr
        tone = (np.sin(2 * np.pi * 40 * t) * 0.004 * 32767).astype("<i2")  # very quiet 40 Hz
        try:
            subprocess.run(
                self.command + ["-t", "raw", "-f", "S16_LE", "-c", "1", "-r", str(sr)],
                input=tone.tobytes(), timeout=10, capture_output=True,
            )
        except Exception as exc:
            log.debug("keep-alive failed: %s", exc)


def player_from_config(section: dict) -> AudioPlayer:
    return AudioPlayer(
        alsa_device=section.get("alsa_device", "auto"),
        bluetooth_mac=str(section.get("bluetooth_mac") or "").strip(),
        keepalive_seconds=float(section.get("bluetooth_keepalive_seconds") or 0),
    )

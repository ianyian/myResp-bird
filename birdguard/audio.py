"""Play a .wav file without blocking (aplay on the Pi, afplay on a Mac)."""

from __future__ import annotations

import logging
import platform
import re
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_CARD_RE = re.compile(r"^card (\d+): (\S+) \[(.*?)\], device (\d+): (.*)$")


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


class AudioPlayer:
    def __init__(self, alsa_device: str = "auto"):
        self._proc: subprocess.Popen | None = None
        self.system = platform.system()
        self.device: str | None = None
        if self.system == "Darwin" and shutil.which("afplay"):
            self.command = ["afplay"]
        elif shutil.which("aplay"):
            self.device = find_usb_alsa_device() if alsa_device == "auto" else alsa_device
            if alsa_device == "auto" and self.device is None:
                log.warning("no USB speaker found - using the default ALSA output")
            self.command = ["aplay", "-q"] + (["-D", self.device] if self.device else [])
        else:
            self.command = []
            log.warning("no audio player found (aplay/afplay) - sounds will be silent")

    def describe(self) -> str:
        if not self.command:
            return "none (silent)"
        return " ".join(self.command)

    def play(self, wav: Path) -> None:
        self.stop()
        if not self.command:
            return
        try:
            self._proc = subprocess.Popen(
                self.command + [str(wav)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
            )
        except Exception as exc:
            log.error("could not start audio playback: %s", exc)

    def is_playing(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        if self.is_playing():
            self._proc.terminate()
        if self._proc is not None:
            try:
                _, err = self._proc.communicate(timeout=2)
                if self._proc.returncode not in (0, -15) and err:
                    log.error("audio player error: %s", err.decode(errors="replace").strip())
            except Exception:
                pass
        self._proc = None

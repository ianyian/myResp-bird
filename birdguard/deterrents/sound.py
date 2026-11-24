from __future__ import annotations

import logging
import time
from pathlib import Path

from ..audio import AudioPlayer
from ..sounds import SoundComposer, write_wav
from .base import Deterrent

log = logging.getLogger(__name__)


class SoundDeterrent(Deterrent):
    name = "sound"

    def __init__(self, section: dict, cfg):
        super().__init__(section, cfg)
        lib = section.get("library_dir")
        self.composer = SoundComposer(
            duration=float(section.get("duration_seconds", 10)),
            sample_rate=int(section.get("sample_rate", 44100)),
            volume=float(section.get("volume", 0.9)),
            use_generated=bool(section.get("use_generated", True)),
            library_dir=cfg.path(lib) if lib else None,
        )
        self.player = AudioPlayer(section.get("alsa_device", "auto"))
        self.tmp_dir = cfg.path(cfg["storage"]["data_dir"]) / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        log.info("sound output: %s", self.player.describe())

    def activate(self) -> dict:
        samples, kinds = self.composer.compose()
        wav = self.tmp_dir / f"sound-{int(time.time() * 1000)}.wav"
        write_wav(wav, samples, self.composer.sr)
        self.player.play(wav)
        self._cleanup(keep=wav)
        log.info("playing %.0fs sound: %s", self.composer.duration, ", ".join(kinds))
        return {"sound": kinds}

    def _cleanup(self, keep: Path) -> None:
        for old in self.tmp_dir.glob("sound-*.wav"):
            if old != keep and time.time() - old.stat().st_mtime > 60:
                old.unlink(missing_ok=True)

    def is_active(self) -> bool:
        return self.player.is_playing()

    def stop(self) -> None:
        self.player.stop()

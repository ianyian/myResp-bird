"""Deterrents = anything that scares birds (speaker, lights, sprinkler...).

To add a new accessory later:
  1. create a class in this package that subclasses `Deterrent`
  2. register it in `REGISTRY` below
  3. add a section with `enabled: true` under `deterrents:` in the config
Nothing else in the program needs to change.
"""

from __future__ import annotations

import logging

from ..config import Config
from .base import Deterrent
from .gpio_output import GpioOutputDeterrent
from .sound import SoundDeterrent

log = logging.getLogger(__name__)

REGISTRY: dict[str, type[Deterrent]] = {
    "sound": SoundDeterrent,
    "gpio_output": GpioOutputDeterrent,
}


def build_deterrents(cfg: Config) -> list[Deterrent]:
    out: list[Deterrent] = []
    for name, section in (cfg.get("deterrents") or {}).items():
        if not section or not section.get("enabled", False):
            continue
        cls = REGISTRY.get(name)
        if cls is None:
            log.warning("unknown deterrent '%s' in config - ignored", name)
            continue
        out.append(cls(section, cfg))
        log.info("deterrent enabled: %s", name)
    return out


__all__ = ["Deterrent", "build_deterrents", "REGISTRY"]

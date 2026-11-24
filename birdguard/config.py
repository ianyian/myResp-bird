"""Load config.yaml, then overlay config.local.yaml if it exists."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class Config(dict):
    """A plain dict plus the folder the config came from (for relative paths)."""

    root: Path

    def path(self, value: str) -> Path:
        p = Path(value).expanduser()
        return p if p.is_absolute() else (self.root / p)


def load_config(path: str | Path, overrides: dict | None = None) -> Config:
    path = Path(path).resolve()
    with open(path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    local = path.with_name("config.local.yaml")
    if local.exists():
        with open(local, "r", encoding="utf-8") as f:
            data = deep_merge(data, yaml.safe_load(f) or {})

    if overrides:
        data = deep_merge(data, overrides)

    validate(data)
    cfg = Config(data)
    cfg.root = path.parent
    return cfg


def validate(cfg: dict) -> None:
    trig = cfg["trigger"]
    if trig["confirm_frames"] > trig["window_frames"]:
        raise ValueError("trigger.confirm_frames must be <= trigger.window_frames")
    sound = cfg.get("deterrents", {}).get("sound", {})
    if sound.get("enabled") and sound["duration_seconds"] > trig["cooldown_seconds"]:
        raise ValueError(
            "deterrents.sound.duration_seconds must be <= trigger.cooldown_seconds "
            "(otherwise sounds could overlap)"
        )

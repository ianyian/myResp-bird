"""Event history (events.jsonl) + snapshot images, kept in the data folder."""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import datetime
from pathlib import Path


class EventLog:
    def __init__(self, data_dir: Path, keep: int = 500):
        self.dir = data_dir
        self.snap_dir = data_dir / "snapshots"
        self.snap_dir.mkdir(parents=True, exist_ok=True)
        self.file = data_dir / "events.jsonl"
        self.keep = keep
        self._lock = threading.Lock()
        self.recent: deque[dict] = deque(maxlen=200)
        self._load()

    def _load(self) -> None:
        if not self.file.exists():
            return
        with open(self.file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    self.recent.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    def add(self, kind: str, when: datetime, jpeg: bytes | None = None, **info) -> dict:
        event_id = when.strftime("%Y%m%d-%H%M%S-%f")
        event = {"id": event_id, "time": when.isoformat(timespec="seconds"), "type": kind, **info}
        if jpeg:
            name = f"{event_id}.jpg"
            (self.snap_dir / name).write_bytes(jpeg)
            event["snapshot"] = name
        with self._lock:
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
            self.recent.append(event)
            self._prune()
        return event

    def _prune(self) -> None:
        snaps = sorted(self.snap_dir.glob("*.jpg"))
        for old in snaps[: max(0, len(snaps) - self.keep)]:
            old.unlink(missing_ok=True)
        # keep the jsonl file from growing forever
        if self.file.stat().st_size > 5_000_000:
            lines = self.file.read_text(encoding="utf-8").splitlines()[-self.keep * 4:]
            self.file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def latest(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self.recent)[-n:][::-1]

    def count_today(self, kind: str, today: datetime) -> int:
        day = today.strftime("%Y-%m-%d")
        with self._lock:
            return sum(1 for e in self.recent if e["type"] == kind and e["time"].startswith(day))

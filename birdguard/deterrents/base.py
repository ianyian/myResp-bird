from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Deterrent(ABC):
    name = "deterrent"

    def __init__(self, section: dict, cfg: Any):
        self.section = section
        self.cfg = cfg

    @abstractmethod
    def activate(self) -> dict:
        """Start scaring. Must return quickly (do slow work in a thread).

        Returns a small dict describing what was done, shown in the event log.
        """

    def is_active(self) -> bool:
        return False

    def stop(self) -> None:
        pass

    def close(self) -> None:
        self.stop()

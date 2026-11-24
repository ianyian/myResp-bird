"""Phone push notifications through ntfy (https://ntfy.sh - free)."""

from __future__ import annotations

import logging
import threading
import time
import urllib.request

log = logging.getLogger(__name__)


class NtfyNotifier:
    def __init__(self, section: dict):
        self.enabled = bool(section.get("enabled"))
        self.server = str(section.get("server", "https://ntfy.sh")).rstrip("/")
        self.topic = str(section.get("topic", ""))
        self.min_interval = float(section.get("min_interval_seconds", 300))
        self.attach = bool(section.get("attach_snapshot", True))
        self.notify_quiet = bool(section.get("notify_quiet_hours", False))
        self._last = 0.0
        if self.enabled and (not self.topic or self.topic == "change-me"):
            log.warning("ntfy enabled but no topic set in config.local.yaml - disabling")
            self.enabled = False

    def notify(self, title: str, message: str, jpeg: bytes | None = None, force: bool = False) -> bool:
        """Send in the background. Rate-limited unless force=True."""
        if not self.enabled:
            return False
        now = time.monotonic()
        if not force and self._last and now - self._last < self.min_interval:
            return False
        self._last = now
        threading.Thread(target=self._send, args=(title, message, jpeg), daemon=True).start()
        return True

    def _send(self, title: str, message: str, jpeg: bytes | None) -> None:
        url = f"{self.server}/{self.topic}"
        title, message = _latin1(title), _latin1(message)  # HTTP headers must be latin-1
        headers = {"Title": title, "Tags": "bird"}
        if jpeg and self.attach:
            headers.update({"Filename": "bird.jpg", "Message": message})
            req = urllib.request.Request(url, data=jpeg, headers=headers, method="PUT")
        else:
            req = urllib.request.Request(url, data=message.encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            log.info("ntfy notification sent")
        except Exception as exc:
            log.warning("ntfy notification failed: %s", exc)


def _latin1(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")

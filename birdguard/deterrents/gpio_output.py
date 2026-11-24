"""Switch a GPIO pin on for N seconds - e.g. a relay driving lights,
a sprinkler valve or another accessory. Template for future add-ons."""

from __future__ import annotations

import logging
import threading

from .base import Deterrent

log = logging.getLogger(__name__)


class GpioOutputDeterrent(Deterrent):
    name = "gpio_output"

    def __init__(self, section: dict, cfg):
        super().__init__(section, cfg)
        from gpiozero import OutputDevice  # only needed on the Pi

        self.seconds = float(section.get("seconds", 10))
        self.device = OutputDevice(
            int(section["pin"]), active_high=bool(section.get("active_high", True)),
            initial_value=False,
        )
        self._timer: threading.Timer | None = None

    def activate(self) -> dict:
        self.stop()
        self.device.on()
        self._timer = threading.Timer(self.seconds, self.device.off)
        self._timer.daemon = True
        self._timer.start()
        return {"gpio_pin": self.section["pin"], "seconds": self.seconds}

    def is_active(self) -> bool:
        return bool(self.device.value)

    def stop(self) -> None:
        if self._timer:
            self._timer.cancel()
        self.device.off()

    def close(self) -> None:
        self.stop()
        self.device.close()

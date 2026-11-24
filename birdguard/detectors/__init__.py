from __future__ import annotations

from ..config import Config
from .base import Detection, Detector


def build_detector(cfg: Config) -> Detector:
    backend = cfg["detector"]["backend"]
    if backend == "hailo":
        from .hailo import HailoDetector
        return HailoDetector(cfg)
    if backend == "simulated":
        from .simulated import SimulatedDetector
        return SimulatedDetector(cfg)
    if backend == "yolo-cpu":
        from .yolo_cpu import YoloCpuDetector
        return YoloCpuDetector(cfg)
    raise ValueError(f"unknown detector backend '{backend}' (use hailo, simulated or yolo-cpu)")


__all__ = ["Detection", "Detector", "build_detector"]

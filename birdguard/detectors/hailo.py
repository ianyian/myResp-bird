"""Raspberry Pi Camera Module 3 + AI HAT+ (Hailo) object detection.

Uses the Hailo helper built into Picamera2 and the YOLO models installed
by the `hailo-all` package (/usr/share/hailo-models/).
"""

from __future__ import annotations

import glob
import logging
from pathlib import Path

import numpy as np

from .base import COCO_LABELS, Detection, Detector

log = logging.getLogger(__name__)

MODEL_DIR = "/usr/share/hailo-models"


def find_model(setting: str) -> str:
    if setting and setting != "auto":
        if not Path(setting).exists():
            raise FileNotFoundError(f"model file not found: {setting}")
        return setting
    # Prefer models compiled for the Hailo-8 (AI HAT+ 26 TOPS), then Hailo-8L.
    for pattern in ("yolov8s_h8.hef", "yolov8m_h8.hef", "yolov8*_h8.hef", "yolov*_h8.hef",
                    "yolov8s_h8l.hef", "yolov*_h8l.hef"):
        hits = sorted(glob.glob(f"{MODEL_DIR}/{pattern}"))
        if hits:
            return hits[0]
    raise FileNotFoundError(
        f"no YOLO .hef model found in {MODEL_DIR}. Install it with: sudo apt install hailo-all"
    )


class HailoDetector(Detector):
    def __init__(self, cfg):
        from libcamera import Transform
        from picamera2 import Picamera2
        from picamera2.devices import Hailo

        d = cfg["detector"]
        self.model_path = find_model(d.get("model", "auto"))
        log.info("loading AI model %s", self.model_path)
        self.hailo = Hailo(self.model_path)
        model_h, model_w, _ = self.hailo.get_input_shape()

        w, h = d.get("camera_size", [1280, 960])
        self.picam2 = Picamera2()
        # Note: in Picamera2 "BGR888" gives pixels in R,G,B order (what we want).
        config = self.picam2.create_preview_configuration(
            main={"size": (w, h), "format": "BGR888"},
            lores={"size": (model_w, model_h), "format": "BGR888"},
            controls={"FrameRate": d.get("framerate", 15)},
            transform=Transform(hflip=bool(d.get("hflip")), vflip=bool(d.get("vflip"))),
        )
        self.picam2.configure(config)
        self.picam2.start()
        try:  # Camera Module 3 has autofocus: keep refocusing continuously.
            from libcamera import controls
            self.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        except Exception:
            pass
        self.threshold = float(d.get("score_threshold", 0.45))

    def read(self) -> tuple[np.ndarray, list[Detection]]:
        request = self.picam2.capture_request()
        try:
            frame = request.make_array("main")
            lores = request.make_array("lores")
        finally:
            request.release()
        output = self.hailo.run(lores)
        return frame, self._parse(output)

    def _parse(self, output) -> list[Detection]:
        # NMS output: one list per class, each row = [y0, x0, y1, x1, score].
        if isinstance(output, dict):
            output = next(iter(output.values()))
        if len(output) == 1 and len(output[0]) == len(COCO_LABELS):  # batch dimension
            output = output[0]
        dets = []
        for class_id, rows in enumerate(output):
            label = COCO_LABELS[class_id] if class_id < len(COCO_LABELS) else str(class_id)
            for row in rows:
                score = float(row[4])
                if score >= self.threshold * 0.5:  # keep weaker ones for the live view
                    y0, x0, y1, x1 = (float(v) for v in row[:4])
                    dets.append(Detection(label, score, (x0, y0, x1, y1)))
        return dets

    def close(self) -> None:
        try:
            self.picam2.stop()
            self.picam2.close()
        finally:
            self.hailo.close()

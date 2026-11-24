"""Optional: real AI detection on a Mac/PC webcam, no Pi needed.

  pip install ultralytics opencv-python
  python -m birdguard run --backend yolo-cpu

Then hold up a photo/video of a bird (e.g. on your phone) to the webcam.
"""

from __future__ import annotations

import numpy as np

from .base import Detection, Detector


class YoloCpuDetector(Detector):
    def __init__(self, cfg):
        try:
            import cv2
            from ultralytics import YOLO
        except ImportError as exc:
            raise SystemExit(
                "yolo-cpu backend needs extra packages: pip install ultralytics opencv-python"
            ) from exc
        self.cv2 = cv2
        d = cfg["detector"]
        model = d.get("model", "auto")
        self.model = YOLO("yolov8n.pt" if model == "auto" or model.endswith(".hef") else model)
        self.cap = cv2.VideoCapture(int(cfg.get("simulation", {}).get("webcam_index", 0)))
        if not self.cap.isOpened():
            raise SystemExit("could not open the webcam (check camera permission for Terminal)")
        self.threshold = float(d.get("score_threshold", 0.45))

    def read(self) -> tuple[np.ndarray, list[Detection]]:
        ok, bgr = self.cap.read()
        if not ok:
            raise RuntimeError("webcam read failed")
        rgb = self.cv2.cvtColor(bgr, self.cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        result = self.model(rgb, verbose=False, conf=self.threshold * 0.5)[0]
        dets = []
        for box in result.boxes:
            x0, y0, x1, y1 = (float(v) for v in box.xyxy[0])
            dets.append(Detection(
                result.names[int(box.cls[0])], float(box.conf[0]), (x0 / w, y0 / h, x1 / w, y1 / h)
            ))
        return rgb, dets

    def close(self) -> None:
        self.cap.release()

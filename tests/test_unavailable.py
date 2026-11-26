"""When the camera / AI HAT can't open, BirdGuard keeps running and retries."""

import numpy as np

from birdguard.detectors.base import Detection, Detector
from birdguard.detectors.unavailable import UnavailableDetector, describe_error


class Good(Detector):
    def read(self):
        return np.zeros((10, 10, 3), np.uint8), [Detection("bird", 0.9, (0, 0, 1, 1))]


def test_retries_until_hardware_works():
    t = [0.0]
    attempts = []

    def factory():
        attempts.append(t[0])
        if len(attempts) < 2:
            raise RuntimeError("libhailort failed with error: 74 (HAILO_OUT_OF_PHYSICAL_DEVICES)")
        return Good()

    det = UnavailableDetector("first error", factory, retry_seconds=30,
                              clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
    frame, dets = det.read()
    assert dets == [] and frame.shape[2] == 3 and det.error == "first error" and attempts == []
    t[0] = 31
    det.read()                      # 1st retry fails
    assert len(attempts) == 1 and "driver" in det.error
    t[0] = 70
    frame, dets = det.read()        # 2nd retry works -> real detections
    assert len(attempts) == 2 and det.error == "" and dets[0].label == "bird"


def test_error_text_explains_hailo_74():
    msg = describe_error(RuntimeError("libhailort failed with error: 74 (HAILO_OUT_OF_PHYSICAL_DEVICES)"))
    assert "driver" in msg

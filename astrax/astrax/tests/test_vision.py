import numpy as np
import cv2

from app.services.vision import VisionEngine


def test_opencv_fallback_detects_colored_object():
    engine = VisionEngine()
    frame1 = np.zeros((360, 640, 3), dtype=np.uint8)
    frame2 = frame1.copy()
    cv2.rectangle(frame1, (180, 150), (280, 250), (0, 0, 255), -1)
    cv2.rectangle(frame2, (230, 170), (330, 270), (0, 0, 255), -1)
    engine.analyze(frame1)
    obs = engine.analyze(frame2)
    assert any(o["label"] == "RED_OBJECT" for o in obs.objects)
    assert obs.activity in {"PICK", "ROTATE", "IDLE"}


def test_observation_timestamp_uses_frame_capture_time():
    engine = VisionEngine()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    engine.analyze(frame, observed_at=123.4)

    assert engine.last_ts == 123.4

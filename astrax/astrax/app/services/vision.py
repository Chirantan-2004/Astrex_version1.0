from __future__ import annotations

import math
import time
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np


@dataclass
class VisionObservation:
    activity: str = "IDLE"
    confidence: float = 0.0
    person_detected: bool = False
    objects: list[dict[str, Any]] = None
    hands: list[dict[str, float]] = None
    interaction: str | None = None
    source: str = "vision"
    note: str = ""
    latency_ms: float = 0.0

    def __post_init__(self):
        if self.objects is None:
            self.objects = []
        if self.hands is None:
            self.hands = []

    def to_dict(self):
        return asdict(self)


class VisionEngine:
    """Hybrid edge perception layer.

    Priority:
      1. Optional Ultralytics pose model when installed.
      2. OpenCV-only fallback for motion + red/yellow object interaction.

    This deliberately does not pretend that a generic pretrained detector is an
    experiment-specific HAR model. The experiment classifier can be trained later
    using the dataset tooling included with the project.
    """

    def __init__(self):
        self.model = None
        self.model_name = None
        self.enabled = True
        self.prev_gray = None
        self.prev_hands: list[tuple[float, float]] = []
        self.prev_objects: dict[str, tuple[float, float]] = {}
        self.last = VisionObservation(note="Waiting for camera frames")
        self.last_ts = 0.0
        self.frame_counter = 0
        self.load_error = None

    def load(self, model_name: str = "yolo26n-pose.pt"):
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_name)
            self.model_name = model_name
            self.load_error = None
            return True
        except Exception as exc:
            self.model = None
            self.model_name = None
            self.load_error = str(exc)
            return False

    @property
    def status(self):
        return {
            "enabled": self.enabled,
            "model_loaded": self.model is not None,
            "model": self.model_name,
            "fallback": self.model is None,
            "load_error": self.load_error,
            "last": self.last.to_dict(),
        }

    def analyze(self, frame, observed_at: float | None = None) -> VisionObservation:
        started = time.perf_counter()
        capture_timestamp = time.monotonic() if observed_at is None else observed_at
        self.frame_counter += 1
        if frame is None:
            return self.last

        h, w = frame.shape[:2]
        objects = self._color_objects(frame)
        hands: list[dict[str, float]] = []
        person = False

        # Run heavyweight pose inference every third frame.
        if self.model is not None and self.frame_counter % 3 == 0:
            try:
                results = self.model.predict(frame, verbose=False, imgsz=416, conf=0.35, max_det=5)
                result = results[0]
                if result.keypoints is not None and len(result.keypoints.xy) > 0:
                    person = True
                    pts = result.keypoints.xy[0].cpu().numpy()
                    # COCO pose indices: left wrist=9, right wrist=10.
                    for idx in (9, 10):
                        if idx < len(pts):
                            x, y = float(pts[idx][0]), float(pts[idx][1])
                            if x > 0 and y > 0:
                                hands.append({"x": x, "y": y, "confidence": 1.0})
                elif result.boxes is not None and len(result.boxes) > 0:
                    person = True
            except Exception as exc:
                self.load_error = f"Inference fallback: {exc}"

        motion = self._motion_score(frame)
        activity, confidence, interaction, note = self._infer_activity(hands, objects, motion, w, h)

        source = "yolo-pose+opencv" if self.model is not None else "opencv-fallback"
        obs = VisionObservation(
            activity=activity,
            confidence=round(confidence, 3),
            person_detected=person,
            objects=objects,
            hands=hands,
            interaction=interaction,
            source=source,
            note=note,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        self.last = obs
        self.last_ts = capture_timestamp
        return obs

    def _color_objects(self, frame):
        import cv2
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        specs = [
            ("RED_OBJECT", ((0, 90, 70), (10, 255, 255)), "red"),
            ("RED_OBJECT", ((170, 90, 70), (179, 255, 255)), "red"),
            ("YELLOW_OBJECT", ((18, 80, 80), (40, 255, 255)), "yellow"),
        ]
        found = []
        for name, (lo, hi), color in specs:
            mask = cv2.inRange(hsv, np.array(lo), np.array(hi))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for c in contours:
                area = cv2.contourArea(c)
                if area < 600:
                    continue
                x, y, w, h = cv2.boundingRect(c)
                if w * h > frame.shape[0] * frame.shape[1] * 0.45:
                    continue
                found.append({"label": name, "color": color, "x": x, "y": y, "w": w, "h": h,
                              "cx": x + w / 2, "cy": y + h / 2, "confidence": min(0.98, 0.55 + area / 30000)})
        # Keep the strongest detection per semantic class.
        best = {}
        for item in found:
            key = item["label"]
            if key not in best or item["confidence"] > best[key]["confidence"]:
                best[key] = item
        return list(best.values())

    def _motion_score(self, frame):
        import cv2
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 90))
        if self.prev_gray is None:
            self.prev_gray = gray
            return 0.0
        diff = cv2.absdiff(gray, self.prev_gray)
        self.prev_gray = gray
        return float(np.mean(diff) / 255.0)

    def _infer_activity(self, hands, objects, motion, width, height):
        # Interaction-driven rules are intentionally conservative.
        if not hands:
            moved = 0.0
            moved_label = None
            for obj in objects:
                key = obj["label"]
                previous = self.prev_objects.get(key)
                if previous:
                    d = math.hypot(obj["cx"] - previous[0], obj["cy"] - previous[1])
                    if d > moved:
                        moved, moved_label = d, key
                self.prev_objects[key] = (obj["cx"], obj["cy"])
            if moved > max(12.0, min(width, height) * 0.025):
                return "PICK", 0.67, moved_label, "Object displacement detected by the OpenCV fallback."
            if motion > 0.025 and objects:
                return "ROTATE", 0.61, objects[0]["label"], "Motion near a detected experiment object; pose backend unavailable."
            if motion < 0.015:
                return "IDLE", 0.82, None, "No stable interaction detected."
            return "IDLE", 0.58, None, "Motion detected; pose backend is unavailable."

        best_distance = 999999.0
        nearest = None
        for hand in hands:
            for obj in objects:
                d = math.hypot(hand["x"] - obj["cx"], hand["y"] - obj["cy"])
                if d < best_distance:
                    best_distance, nearest = d, obj

        diag = math.hypot(width, height)
        norm_d = best_distance / diag if nearest else 1.0
        if nearest and norm_d < 0.10:
            # If the hand is very close to an object and there is movement, treat it
            # as a pickup/manipulation interaction. Target-zone placement is inferred
            # when the interaction is near the central target region.
            center_d = math.hypot(nearest["cx"] - width / 2, nearest["cy"] - height / 2) / diag
            if center_d < 0.18 and motion > 0.008:
                return "INSERT", 0.86, nearest["label"], "Hand-object interaction detected in target zone."
            if motion > 0.006:
                return "PICK", 0.82, nearest["label"], "Hand approaching/interacting with experiment object."
            return "PICK", 0.72, nearest["label"], "Hand is close to experiment object."

        if motion > 0.025 and nearest:
            return "ROTATE", 0.68, nearest["label"], "Sustained manipulation motion near detected object."
        if motion < 0.012:
            return "IDLE", 0.82, None, "No significant interaction detected."
        return "IDLE", 0.62, None, "Motion present without a sufficiently confident interaction."

    def annotate(self, frame):
        import cv2
        obs = self.last
        out = frame.copy()
        for obj in obs.objects:
            x, y, w, h = map(int, (obj["x"], obj["y"], obj["w"], obj["h"]))
            bgr = (0, 210, 255) if obj["color"] == "yellow" else (30, 80, 255)
            cv2.rectangle(out, (x, y), (x+w, y+h), bgr, 2)
            cv2.putText(out, f'{obj["label"]} {obj["confidence"]*100:.0f}%', (x, max(18, y-7)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, bgr, 2)
        for hand in obs.hands:
            cv2.circle(out, (int(hand["x"]), int(hand["y"])), 7, (70, 230, 255), -1)
            cv2.putText(out, "HAND", (int(hand["x"])+8, int(hand["y"])-8), cv2.FONT_HERSHEY_SIMPLEX, .45, (70,230,255), 1)
        cv2.rectangle(out, (10, 10), (350, 88), (5, 12, 20), -1)
        cv2.putText(out, f"ACTIVITY  {obs.activity}", (22, 38), cv2.FONT_HERSHEY_SIMPLEX, .75, (80,230,255), 2)
        cv2.putText(out, f"CONF      {obs.confidence*100:.1f}%", (22, 63), cv2.FONT_HERSHEY_SIMPLEX, .6, (90,240,160), 2)
        cv2.putText(out, f"ENGINE    {obs.source}", (22, 82), cv2.FONT_HERSHEY_SIMPLEX, .42, (170,190,205), 1)
        return out

"""AI orchestration for the ASTRAX prototype.

This module turns the optional perception backends and activity heuristics into a
single, clearer integration point for the app and future model-driven upgrades.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIModelStatus:
    model: str
    supported: bool
    ready: bool
    fallback: bool
    note: str = ""


class AIIntegration:
    """Clean abstraction over optional AI packages and fallback perception."""

    def __init__(self):
        self.model = "opencv-fallback"
        self.supported = False
        self.ready = True
        self.fallback = True
        self.note = "OpenCV fallback is active; optional YOLO/MediaPipe can be enabled for richer perception."

        try:
            import ultralytics  # noqa: F401
            self.model = "yolo-pose"
            self.supported = True
            self.fallback = False
            self.note = "Ultralytics YOLO pose support detected."
        except Exception:
            self.supported = False
            self.fallback = True

    def status(self):
        return {
            "model": self.model,
            "supported": self.supported,
            "ready": self.ready,
            "fallback": self.fallback,
            "note": self.note,
        }

    def analyze_frame(self, vision_engine, frame):
        if frame is None:
            return None
        if vision_engine is None:
            return None
        return vision_engine.analyze(frame)

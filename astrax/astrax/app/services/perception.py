"""Optional real CV adapters.

The dashboard does not require these packages. They are intentionally isolated so the
prototype can run in Demo Mode on a normal laptop while the real perception pipeline
can be enabled on a machine with compatible CV/ML packages.
"""


class OptionalPerception:
    def __init__(self):
        self.yolo_available = False
        self.mediapipe_available = False
        self.errors = {}

        try:
            from ultralytics import YOLO  # noqa: F401
            self.yolo_available = True
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.errors["yolo"] = str(exc)

        try:
            import mediapipe  # noqa: F401
            self.mediapipe_available = True
        except Exception as exc:  # pragma: no cover - optional dependency path
            self.errors["mediapipe"] = str(exc)

    @property
    def status(self):
        return {
            "yolo": self.yolo_available,
            "mediapipe": self.mediapipe_available,
            "ready": self.yolo_available or self.mediapipe_available,
            "errors": self.errors,
        }

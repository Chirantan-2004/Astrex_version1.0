"""Download the optional local YOLO pose model through Ultralytics."""
import sys
from pathlib import Path

MODEL = "yolo26n-pose.pt"

try:
    from ultralytics import YOLO
except Exception as exc:
    print("Ultralytics is not installed. Install requirements-ai.txt first.")
    print(exc)
    sys.exit(1)

print(f"Loading {MODEL}. Ultralytics will cache/download the weight when needed.")
model = YOLO(MODEL)
print(f"Model ready: {MODEL}")
print(f"Project model directory: {Path('models').resolve()}")

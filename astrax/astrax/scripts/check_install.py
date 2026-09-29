"""Print a concise environment readiness report."""
import importlib.util
import platform
import sys

packages = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "cv2",
    "numpy",
    "pandas",
    "sklearn",
    "joblib",
    "pyttsx3",
    "ultralytics",
    "mediapipe",
]
print("ASTRAX environment check")
print(f"Python: {sys.version.split()[0]} ({platform.system()})")
for package in packages:
    print(f"{'OK ' if importlib.util.find_spec(package) else 'MISS'} {package}")
print("\nCore runtime requires: fastapi, uvicorn, pydantic.")
print("AI camera path benefits from: opencv-python, numpy, pandas, ultralytics, scikit-learn, joblib, pyttsx3.")

from __future__ import annotations

import threading
import time
import os
from pathlib import Path


class VideoService:
    def __init__(self, vision=None):
        self.running = False
        self.recording = False
        self.cap = None
        self.writer = None
        self.lock = threading.Lock()
        self._lifecycle_lock = threading.Lock()
        if os.getenv("ASTRO_VIDEO_DIR"):
            self.output_dir = Path(os.environ["ASTRO_VIDEO_DIR"])
        elif os.getenv("VERCEL"):
            self.output_dir = Path("/tmp/astrax/experiments")
        else:
            self.output_dir = Path(__file__).resolve().parents[2] / "data" / "experiments"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vision = vision
        self.last_frame = None
        self.camera_index = 0
        self.error = None
        self.frames_seen = 0
        self.fps = 0.0
        self._thread = None
        self._stop = threading.Event()
        self.on_observation = None

    def start_camera(self, index: int = 0):
        with self._lifecycle_lock:
            return self._start_camera(index)

    def _start_camera(self, index: int):
        self._stop_camera()
        if self._thread is not None and self._thread.is_alive():
            self.error = "Previous camera capture is still shutting down."
            return False
        try:
            import cv2
            candidates = []
            seen = set()
            for candidate in [index, 0, 1, 2, 3, 4, 5, 6]:
                if candidate not in seen:
                    seen.add(candidate)
                    candidates.append(candidate)

            cap = None
            chosen_index = index
            for candidate in candidates:
                try:
                    cap = cv2.VideoCapture(candidate, cv2.CAP_DSHOW if hasattr(cv2, 'CAP_DSHOW') else 0)
                except Exception:
                    cap = None
                if cap is not None and cap.isOpened():
                    chosen_index = candidate
                    break
                if cap is not None:
                    cap.release()
                    cap = None

                try:
                    cap = cv2.VideoCapture(candidate)
                except Exception:
                    cap = None
                if cap is not None and cap.isOpened():
                    chosen_index = candidate
                    break
                if cap is not None:
                    cap.release()
                    cap = None

            if cap is None or not cap.isOpened():
                self.error = f"Camera {index} could not be opened."
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)
            stop_event = threading.Event()
            thread = threading.Thread(target=self._capture_loop, args=(stop_event, cap), daemon=True)
            with self.lock:
                self.cap = cap
                self.running = True
                self.camera_index = chosen_index
                self.error = None
                self._stop = stop_event
                self._thread = thread
            thread.start()
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def stop_camera(self):
        with self._lifecycle_lock:
            self._stop_camera()

    def _stop_camera(self):
        self._stop.set()
        with self.lock:
            thread = self._thread
            cap = self.cap
            self.running = False
            self.cap = None
            if self.writer is not None:
                self.writer.release()
            self.writer = None
            self.recording = False
        if cap is not None:
            cap.release()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
        with self.lock:
            if self._thread is thread and thread is not None and not thread.is_alive():
                self._thread = None

    def start_recording(self, experiment_id: str):
        try:
            import cv2
            with self.lock:
                if self.cap is None:
                    return False
                width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
                height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
                fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 20)
                if fps < 5 or fps > 60:
                    fps = 20
                path = self.output_dir / f"{experiment_id}.mp4"
                self.writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
                self.recording = bool(self.writer.isOpened())
                return self.recording
        except Exception as exc:
            self.error = str(exc)
            return False

    def stop_recording(self):
        with self.lock:
            if self.writer is not None:
                self.writer.release()
            self.writer = None
            self.recording = False

    def _capture_loop(self, stop_event: threading.Event, cap):
        import cv2
        last = time.perf_counter()
        counter = 0
        failed_reads = 0
        max_failed_reads = 10
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok or frame is None:
                failed_reads += 1
                if failed_reads >= max_failed_reads:
                    self.error = "Camera frame read failed."
                    break
                time.sleep(0.05)
                continue
            failed_reads = 0
            if self.vision is not None:
                try:
                    observation = self.vision.analyze(frame, observed_at=time.monotonic())
                    frame = self.vision.annotate(frame)
                    if self.on_observation is not None:
                        self.on_observation(observation)
                except Exception as exc:
                    self.error = f"Vision error: {exc}"
            with self.lock:
                if self.cap is cap and not stop_event.is_set():
                    self.last_frame = frame
                if self.writer is not None and self.recording:
                    self.writer.write(frame)
            counter += 1
            now = time.perf_counter()
            if now - last >= 1:
                self.fps = counter / (now - last)
                counter = 0
                last = now
            self.frames_seen += 1
        with self.lock:
            if self.cap is cap:
                self.running = False
            if self._thread is threading.current_thread():
                self._thread = None

    def frames(self):
        import cv2
        while self.running:
            with self.lock:
                frame = None if self.last_frame is None else self.last_frame.copy()
            if frame is not None:
                ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 86])
                if ok:
                    yield b'--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n' + encoded.tobytes() + b'\r\n'
            time.sleep(0.03)

    @property
    def status(self):
        return {
            "running": self.running,
            "recording": self.recording,
            "camera_index": self.camera_index,
            "fps": round(self.fps, 1),
            "frames_seen": self.frames_seen,
            "error": self.error,
        }

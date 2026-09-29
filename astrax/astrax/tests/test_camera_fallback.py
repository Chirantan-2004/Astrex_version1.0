import sys
import types

from app.services.video import VideoService


class FakeCapture:
    def __init__(self, open_result, read_result=(True, None)):
        self.open_result = open_result
        self.closed = False
        self._read_result = read_result

    def isOpened(self):
        return self.open_result

    def release(self):
        self.closed = True

    def set(self, *args, **kwargs):
        return True

    def get(self, *args, **kwargs):
        return 0

    def read(self):
        return self._read_result


def test_video_service_falls_back_to_other_camera_indices(monkeypatch):
    fake_cv2 = types.SimpleNamespace(
        VideoCapture=lambda index, *args, **kwargs: FakeCapture(index == 2),
        CAP_DSHOW=130,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    service = VideoService()
    ok = service.start_camera(0)

    assert ok is True
    assert service.camera_index == 2
    assert service.running is True


def test_restarting_camera_releases_the_previous_capture(monkeypatch):
    captures = []

    def open_capture(*args, **kwargs):
        capture = FakeCapture(True, read_result=(False, None))
        captures.append(capture)
        return capture

    fake_cv2 = types.SimpleNamespace(
        VideoCapture=open_capture,
        CAP_DSHOW=130,
        CAP_PROP_FRAME_WIDTH=3,
        CAP_PROP_FRAME_HEIGHT=4,
        CAP_PROP_FPS=5,
    )
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    service = VideoService()
    assert service.start_camera(0) is True
    previous_capture = service.cap

    assert service.start_camera(0) is True
    assert previous_capture.closed is True
    assert service.cap is not previous_capture
    service.stop_camera()

import threading

_engine = None
_lock = threading.Lock()
_last_error = None

try:
    import pyttsx3  # type: ignore
except Exception as exc:  # pragma: no cover - optional dependency path
    pyttsx3 = None
    _last_error = str(exc)


def speak(text: str) -> bool:
    global _engine, _last_error
    if not text or not text.strip():
        return False
    if pyttsx3 is None:
        _last_error = "pyttsx3 is not installed."
        return False

    def _run():
        global _engine, _last_error
        try:
            with _lock:
                if _engine is None:
                    _engine = pyttsx3.init()
                _engine.say(text)
                _engine.runAndWait()
            _last_error = None
        except Exception as exc:  # pragma: no cover - OS voice backend varies
            _last_error = str(exc)

    threading.Thread(target=_run, daemon=True).start()
    return True

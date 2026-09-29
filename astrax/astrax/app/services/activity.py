from collections import deque
import time

class TemporalActivityFilter:
    """Confirms an activity only after N consecutive observations agree."""
    def __init__(self, window: int = 3, min_confidence: float = 0.70, max_window_seconds: float = 1.0):
        self.window = window
        self.min_confidence = min_confidence
        self.max_window_seconds = max_window_seconds
        self.history = deque(maxlen=window)
        self.last_observed_at: float | None = None

    def observe(self, activity: str, confidence: float, observed_at: float | None = None):
        timestamp = time.monotonic() if observed_at is None else observed_at
        if self.last_observed_at is not None and timestamp <= self.last_observed_at:
            if timestamp < self.last_observed_at:
                self.history.clear()
            return None
        self.last_observed_at = timestamp
        if confidence < self.min_confidence:
            self.history.clear()
            return None
        if activity.upper() == "IDLE":
            self.history.clear()
            return None
        while self.history and timestamp - self.history[0][1] > self.max_window_seconds:
            self.history.popleft()
        self.history.append((activity.upper(), timestamp))
        activities = [item[0] for item in self.history]
        if len(activities) == self.window and len(set(activities)) == 1:
            confirmed = activities[-1]
            self.history.clear()
            return confirmed
        return None

    def clear_history(self, observed_at: float | None = None):
        self.history.clear()
        if observed_at is not None and (self.last_observed_at is None or observed_at > self.last_observed_at):
            self.last_observed_at = observed_at

    def reset(self):
        self.history.clear()
        self.last_observed_at = None

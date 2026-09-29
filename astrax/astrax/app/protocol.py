from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

PROTOCOL = [
    {"step": 1, "activity": "OPEN", "instruction": "Open the experiment container"},
    {"step": 2, "activity": "PICK", "instruction": "Pick the experiment object"},
    {"step": 3, "activity": "INSERT", "instruction": "Insert the object into the target"},
    {"step": 4, "activity": "ROTATE", "instruction": "Rotate the object"},
    {"step": 5, "activity": "CLOSE", "instruction": "Close the experiment container"},
]

@dataclass
class ProtocolEngine:
    protocol: list[dict] = field(default_factory=lambda: [dict(x) for x in PROTOCOL])
    index: int = 0
    status: str = "READY"
    started_at: str | None = None
    last_message: str = "System ready."
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.index >= len(self.protocol)

    @property
    def expected(self) -> str | None:
        return None if self.complete else self.protocol[self.index]["activity"]

    def start(self) -> None:
        self.index = 0
        self.status = "RUNNING"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.last_message = f"Next action: {self.protocol[0]['instruction']}."
        self.events.clear()

    def reset(self) -> None:
        self.index = 0
        self.status = "READY"
        self.started_at = None
        self.last_message = "System ready."
        self.events.clear()

    def observe(self, activity: str, confidence: float, source: str = "demo") -> dict:
        activity = activity.upper().strip()
        now = datetime.now(timezone.utc).isoformat()
        if self.complete:
            result = self._event(now, activity, confidence, "COMPLETE", "Experiment already complete.", source)
            self.events.append(result)
            return result
        expected = self.expected
        if activity == expected:
            step = self.index + 1
            self.index += 1
            if self.complete:
                self.status = "COMPLETED"
                self.last_message = "Experiment completed successfully."
                state = "COMPLETE"
                message = "Step verified. Experiment complete."
            else:
                self.status = "RUNNING"
                next_item = self.protocol[self.index]
                self.last_message = f"Next action: {next_item['instruction']}."
                state = "VALID"
                message = f"Step {step} verified."
            result = self._event(now, activity, confidence, state, message, source, step)
        else:
            self.status = "ALERT"
            next_instruction = self.protocol[self.index]["instruction"]
            state = "OUT_OF_ORDER"
            message = f"Expected {expected}; detected {activity}. Recommended action: {next_instruction}."
            self.last_message = message
            result = self._event(now, activity, confidence, state, message, source, self.index + 1)
        self.events.append(result)
        return result

    @staticmethod
    def _event(timestamp: str, activity: str, confidence: float, status: str, message: str, source: str, step: int = 0) -> dict:
        return {
            "timestamp": timestamp,
            "step": step,
            "expected_activity": None,
            "detected_activity": activity,
            "confidence": round(confidence, 4),
            "status": status,
            "message": message,
            "source": source,
        }

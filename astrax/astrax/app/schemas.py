from datetime import datetime
from pydantic import BaseModel, Field, field_validator

ACTIVITIES = ["IDLE", "OPEN", "PICK", "INSERT", "ROTATE", "CLOSE"]

class ActivityObservation(BaseModel):
    activity: str
    confidence: float = Field(ge=0, le=1)
    source: str = "demo"


class CommunicationCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value

class ExperimentStatus(BaseModel):
    experiment_id: str
    name: str
    status: str
    current_step: int
    total_steps: int
    expected_activity: str | None
    detected_activity: str | None
    confidence: float
    protocol: list[dict]
    events: list[dict]
    last_message: str
    offline: bool
    recording: bool
    stream_available: bool
    started_at: str | None

class ProtocolEvent(BaseModel):
    timestamp: str
    step: int
    expected_activity: str | None
    detected_activity: str
    confidence: float
    status: str
    message: str

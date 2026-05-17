from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class EventType(StrEnum):
    LOG = "log"
    ACTION = "action"
    OBSERVATION = "observation"
    STATUS = "status"
    ERROR = "error"
    DECISION = "decision"


@dataclass(frozen=True, slots=True)
class AgentEvent:
    event_id: str
    event_type: EventType
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict = field(default_factory=dict)

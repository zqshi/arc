from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.agent.value_objects import (
    VALID_SESSION_TRANSITIONS,
    AgentType,
    SessionStatus,
)


class InvalidSessionTransition(Exception):
    def __init__(self, current: SessionStatus, target: SessionStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition agent session from {current!r} to {target!r}")


@dataclass
class AgentSession:
    todo_id: uuid.UUID
    phase_id: uuid.UUID
    agent_type: AgentType
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    external_session_id: str = ""
    status: SessionStatus = SessionStatus.PENDING
    task_context: dict = field(default_factory=dict)
    result_summary: dict = field(default_factory=dict)
    error_reason: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _transition_to(self, target: SessionStatus) -> None:
        allowed = VALID_SESSION_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidSessionTransition(self.status, target)
        self.status = target
        self.updated_at = datetime.now(UTC)

    def start(self, external_session_id: str) -> None:
        self._transition_to(SessionStatus.RUNNING)
        self.external_session_id = external_session_id
        self.started_at = datetime.now(UTC)

    def pause(self) -> None:
        self._transition_to(SessionStatus.PAUSED)

    def resume(self) -> None:
        self._transition_to(SessionStatus.RUNNING)

    def complete(self, result_summary: dict | None = None) -> None:
        self._transition_to(SessionStatus.COMPLETED)
        if result_summary:
            self.result_summary = result_summary
        self.completed_at = datetime.now(UTC)

    def mark_error(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("Error reason is required")
        self._transition_to(SessionStatus.ERROR)
        self.error_reason = reason
        self.completed_at = datetime.now(UTC)

    def cancel(self) -> None:
        self._transition_to(SessionStatus.CANCELLED)
        self.completed_at = datetime.now(UTC)

    def retry(self) -> None:
        self._transition_to(SessionStatus.PENDING)
        self.external_session_id = ""
        self.error_reason = ""
        self.started_at = None
        self.completed_at = None

    @property
    def is_terminal(self) -> bool:
        return self.status in (SessionStatus.COMPLETED, SessionStatus.ERROR, SessionStatus.CANCELLED)

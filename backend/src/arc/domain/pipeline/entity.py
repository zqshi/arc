from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.pipeline.value_objects import (
    VALID_PHASE_TRANSITIONS,
    PhaseStatus,
    PhaseType,
)


class InvalidPhaseTransition(Exception):
    def __init__(self, current: PhaseStatus, target: PhaseStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition phase from {current!r} to {target!r}")


@dataclass
class PipelinePhase:
    todo_id: uuid.UUID
    phase_type: PhaseType
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: PhaseStatus = PhaseStatus.PENDING
    conversation_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _transition_to(self, target: PhaseStatus) -> None:
        allowed = VALID_PHASE_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidPhaseTransition(self.status, target)
        self.status = target
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        self._transition_to(PhaseStatus.ACTIVE)

    def mark_awaiting_confirm(self) -> None:
        self._transition_to(PhaseStatus.AWAITING_CONFIRM)

    def confirm(self) -> None:
        self._transition_to(PhaseStatus.CONFIRMED)

    def skip(self) -> None:
        self._transition_to(PhaseStatus.SKIPPED)

    def reset_for_rollback(self) -> None:
        """Reset to ACTIVE when rolling back to this phase."""
        if self.status in (PhaseStatus.CONFIRMED, PhaseStatus.SKIPPED):
            self._transition_to(PhaseStatus.ACTIVE)

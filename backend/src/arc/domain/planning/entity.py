from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.planning.value_objects import (
    VALID_PLANNING_TRANSITIONS,
    DeliverableStatus,
    DocumentStatus,
    PlanningStatus,
)


@dataclass
class Document:
    project_id: uuid.UUID
    filename: str
    content_type: str
    size: int
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    storage_path: str = ""
    extracted_text: str = ""
    parsed_features: list[dict] = field(default_factory=list)
    status: DocumentStatus = DocumentStatus.UPLOADING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING

    def mark_ready(self, extracted_text: str, features: list[dict]) -> None:
        self.extracted_text = extracted_text
        self.parsed_features = features
        self.status = DocumentStatus.READY

    def mark_error(self) -> None:
        self.status = DocumentStatus.ERROR


@dataclass
class PlanningSession:
    project_id: uuid.UUID
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    version_id: uuid.UUID | None = None
    document_ids: list[uuid.UUID] = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    roadmap: dict = field(default_factory=dict)
    conversation_id: uuid.UUID | None = None
    status: PlanningStatus = PlanningStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def _transition_to(self, target: PlanningStatus) -> None:
        allowed = VALID_PLANNING_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(
                f"Cannot transition planning from {self.status!r} to {target!r}"
            )
        self.status = target
        self.updated_at = datetime.now(UTC)

    def submit_for_review(self, roadmap: dict) -> None:
        self.roadmap = roadmap
        self._transition_to(PlanningStatus.REVIEWING)

    def confirm(self) -> None:
        self._transition_to(PlanningStatus.CONFIRMED)

    def apply(self) -> None:
        self._transition_to(PlanningStatus.APPLIED)

    def revise(self) -> None:
        self._transition_to(PlanningStatus.DRAFT)

    def update_constraints(self, constraints: dict) -> None:
        self.constraints = constraints
        self.updated_at = datetime.now(UTC)


@dataclass
class DeliverableTracker:
    todo_id: uuid.UUID
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    required: list[str] = field(default_factory=list)
    deliverables: dict[str, DeliverableStatus] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def initialize(self, required_types: list[str]) -> None:
        self.required = required_types
        self.deliverables = {t: DeliverableStatus.PENDING for t in required_types}

    def mark_in_progress(self, artifact_type: str) -> None:
        if artifact_type in self.deliverables:
            self.deliverables[artifact_type] = DeliverableStatus.IN_PROGRESS
            self.updated_at = datetime.now(UTC)

    def mark_produced(self, artifact_type: str) -> None:
        self.deliverables[artifact_type] = DeliverableStatus.PRODUCED
        self.updated_at = datetime.now(UTC)

    def mark_confirmed(self, artifact_type: str) -> None:
        if artifact_type in self.deliverables:
            self.deliverables[artifact_type] = DeliverableStatus.CONFIRMED
            self.updated_at = datetime.now(UTC)

    @property
    def completion_pct(self) -> float:
        if not self.deliverables:
            return 0.0
        done = sum(
            1 for s in self.deliverables.values()
            if s in (DeliverableStatus.PRODUCED, DeliverableStatus.CONFIRMED)
        )
        return round(done / len(self.deliverables), 2)

    @property
    def is_complete(self) -> bool:
        return all(
            s in (DeliverableStatus.PRODUCED, DeliverableStatus.CONFIRMED)
            for s in self.deliverables.values()
        ) if self.deliverables else False

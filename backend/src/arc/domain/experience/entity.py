from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.todo.value_objects import (
    ExperienceCategory,
    ExperienceScope,
    ExperienceSource,
    ExperienceStatus,
    Tag,
)

STALE_THRESHOLD = 0.3


@dataclass
class Experience:
    title: str
    problem: str
    solution: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    todo_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    source_experience_id: uuid.UUID | None = None
    scope: ExperienceScope = ExperienceScope.PROJECT
    status: ExperienceStatus = ExperienceStatus.DRAFT
    category: ExperienceCategory = ExperienceCategory.TECHNICAL
    source: ExperienceSource = ExperienceSource.MANUAL
    decisions: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    applicable_scenarios: str = ""
    tags: list[Tag] = field(default_factory=list)
    embedding: list[float] | None = None
    confidence: float = 0.0
    reuse_count: int = 0
    half_life_days: int = 180
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_stale(self) -> bool:
        return self.confidence < STALE_THRESHOLD

    def compute_decayed_confidence(self, original_confidence: float | None = None) -> float:
        base = original_confidence if original_confidence is not None else self.confidence
        if self.half_life_days <= 0:
            return base
        days_elapsed = (datetime.now(UTC) - self.created_at).days
        if days_elapsed <= 0:
            return base
        decay = math.pow(0.5, days_elapsed / self.half_life_days)
        return round(base * decay, 4)

    def confirm(self) -> None:
        if self.status == ExperienceStatus.ARCHIVED:
            raise ValueError("Cannot confirm an archived experience")
        self.status = ExperienceStatus.CONFIRMED
        self.updated_at = datetime.now(UTC)

    def archive(self) -> None:
        self.status = ExperienceStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)

    def promote_to_personal(self) -> None:
        if self.scope == ExperienceScope.PERSONAL:
            raise ValueError("Already a personal experience")
        self.scope = ExperienceScope.PERSONAL
        self.updated_at = datetime.now(UTC)

    def increment_reuse(self) -> None:
        self.reuse_count += 1
        self.updated_at = datetime.now(UTC)

    def update_confidence(self, score: float) -> None:
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {score}")
        self.confidence = score
        self.updated_at = datetime.now(UTC)

    def apply_feedback(self, helpful: bool) -> None:
        if helpful:
            self.confidence = min(1.0, round(self.confidence + 0.05, 3))
            self.reuse_count += 1
        else:
            self.confidence = max(0.0, round(self.confidence - 0.1, 3))
        self.updated_at = datetime.now(UTC)

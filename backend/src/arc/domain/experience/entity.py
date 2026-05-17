from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.todo.value_objects import ExperienceScope, Tag


@dataclass
class Experience:
    title: str
    problem: str
    solution: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    todo_id: uuid.UUID | None = None
    scope: ExperienceScope = ExperienceScope.TODO
    decisions: list[str] = field(default_factory=list)
    pitfalls: list[str] = field(default_factory=list)
    applicable_scenarios: str = ""
    tags: list[Tag] = field(default_factory=list)
    embedding: list[float] | None = None
    confidence: float = 0.0
    reuse_count: int = 0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def increment_reuse(self) -> None:
        """Bump the reuse_count by 1."""
        self.reuse_count += 1
        self.updated_at = datetime.now(UTC)

    def update_confidence(self, score: float) -> None:
        """Update the confidence score. Must be between 0.0 and 1.0."""
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {score}")
        self.confidence = score
        self.updated_at = datetime.now(UTC)

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.artifact.value_objects import ArtifactType


@dataclass
class Artifact:
    todo_id: uuid.UUID
    phase_id: uuid.UUID
    artifact_type: ArtifactType
    content: dict = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    version: int = 1
    is_confirmed: bool = False
    confirmed_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_content(self, new_content: dict) -> None:
        if new_content == self.content:
            return
        self.content = new_content
        self.version += 1
        self.is_confirmed = False
        self.confirmed_at = None
        self.updated_at = datetime.now(UTC)

    def confirm(self) -> None:
        if not self.content:
            raise ValueError("Cannot confirm an artifact with empty content")
        self.is_confirmed = True
        self.confirmed_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def unconfirm(self) -> None:
        self.is_confirmed = False
        self.confirmed_at = None
        self.updated_at = datetime.now(UTC)

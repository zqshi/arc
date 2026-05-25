from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PhaseResponse(BaseModel):
    id: str
    todo_id: str
    phase_type: str
    status: str
    conversation_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ArtifactResponse(BaseModel):
    id: str
    todo_id: str
    phase_id: str
    artifact_type: str
    content: dict[str, Any]
    version: int
    is_confirmed: bool
    confirmed_at: datetime | None = None
    preview_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PipelineStateResponse(BaseModel):
    todo_id: str
    current_phase: str | None
    phases: list[PhaseResponse]
    artifacts: list[ArtifactResponse]


class UpdateArtifactRequest(BaseModel):
    content: dict[str, Any]


class RollbackRequest(BaseModel):
    target_phase: str

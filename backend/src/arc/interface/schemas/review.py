"""评审反馈 API schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewFeedbackResponse(BaseModel):
    id: str
    project_id: str
    source_todo_id: str | None = None
    model_version: int = 0
    scope: str
    status: str
    issue: dict
    resolution_note: str = ""
    created_at: str
    resolved_at: str | None = None


class ReviewFeedbackResolveRequest(BaseModel):
    action: str = Field(..., pattern="^(accept|defer|reject)$")
    note: str = ""


class DomainModelRollbackRequest(BaseModel):
    to_version: int = Field(..., ge=0)


class DomainModelSnapshotResponse(BaseModel):
    version: int
    trigger: str
    trigger_todo_id: str
    created_at: str

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


class ImpactAnalysisRequest(BaseModel):
    affected_aggregates: list[str] = Field(..., min_length=1)
    change_scope: str = Field(..., pattern="^(additive|structural|breaking)$")


class ImpactReportResponse(BaseModel):
    project_id: str
    affected_aggregates: list[str]
    change_scope: str
    max_risk: str
    blocked_count: int
    summary: str
    items: list[dict]

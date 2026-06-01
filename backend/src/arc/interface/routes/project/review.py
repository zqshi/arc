"""评审反馈 + 领域模型历史 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.application.review.service import ReviewService
from arc.domain.project.value_objects import ModelChangeTrigger
from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.review import ReviewFeedbackRepository
from arc.domain.review.value_objects import ReviewFeedbackStatus
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.review import (
    DomainModelRollbackRequest,
    DomainModelSnapshotResponse,
    ReviewFeedbackResolveRequest,
    ReviewFeedbackResponse,
)

router = APIRouter()


# ── Review Feedbacks ─────────────────────────────────────


@router.get(
    "/{project_id}/review-feedbacks",
    response_model=list[ReviewFeedbackResponse],
)
async def list_review_feedbacks(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
):
    repo = ReviewFeedbackRepository(db)
    filter_status = ReviewFeedbackStatus(status) if status else None
    feedbacks = await repo.list_by_project(
        project_id, status=filter_status, skip=skip, limit=limit,
    )
    return [_feedback_resp(fb) for fb in feedbacks]


@router.patch(
    "/{project_id}/review-feedbacks/{feedback_id}",
    response_model=ReviewFeedbackResponse,
)
async def resolve_review_feedback(
    project_id: uuid.UUID,
    feedback_id: uuid.UUID,
    body: ReviewFeedbackResolveRequest,
    db: DbSession,
    user: CurrentUser,
):
    repo = ReviewFeedbackRepository(db)
    svc = ReviewService(repo)
    try:
        fb = await svc.resolve_feedback(feedback_id, body.action, body.note)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _feedback_resp(fb)


# ── Domain Model History ─────────────────────────────────


@router.get(
    "/{project_id}/domain-model/history",
    response_model=list[DomainModelSnapshotResponse],
)
async def list_domain_model_history(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return [
        DomainModelSnapshotResponse(
            version=snap.get("version", 0),
            trigger=snap.get("trigger", ""),
            trigger_todo_id=snap.get("trigger_todo_id", ""),
            created_at=snap.get("created_at", ""),
        )
        for snap in project.domain_model_history
    ]


@router.post("/{project_id}/domain-model/rollback")
async def rollback_domain_model(
    project_id: uuid.UUID,
    body: DomainModelRollbackRequest,
    db: DbSession,
    user: CurrentUser,
):
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    try:
        project.rollback_domain_model(body.to_version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await project_repo.update(project)
    return {"ok": True, "version": project.domain_model_version}


def _feedback_resp(fb) -> dict:
    return {
        "id": str(fb.id),
        "project_id": str(fb.project_id),
        "source_todo_id": str(fb.source_todo_id) if fb.source_todo_id else None,
        "model_version": fb.model_version,
        "scope": fb.scope.value if hasattr(fb.scope, "value") else fb.scope,
        "status": fb.status.value if hasattr(fb.status, "value") else fb.status,
        "issue": {
            "severity": fb.issue.severity.value,
            "category": fb.issue.category.value,
            "title": fb.issue.title,
            "detail": fb.issue.detail,
            "suggestion": fb.issue.suggestion,
        },
        "resolution_note": fb.resolution_note,
        "created_at": fb.created_at.isoformat() if fb.created_at else "",
        "resolved_at": fb.resolved_at.isoformat() if fb.resolved_at else None,
    }

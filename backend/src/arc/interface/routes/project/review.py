"""评审反馈 + 领域模型历史 API 路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.application.review.impact_analyzer import ImpactAnalyzer
from arc.application.review.orchestrator import ModelUpgradeOrchestrator
from arc.application.review.service import ReviewService
from arc.domain.review.value_objects import ModelChangeScope, ReviewFeedbackStatus, UpgradeStrategy
from arc.infrastructure.repositories.artifact import ArtifactRepository as ArtifactRepoImpl
from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.review import ReviewFeedbackRepository
from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.review import (
    DomainModelRollbackRequest,
    DomainModelSnapshotResponse,
    ImpactAnalysisRequest,
    ImpactReportResponse,
    ModelUpgradeRequest,
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
    fb = await svc.resolve_feedback(feedback_id, body.action, body.note)
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


# ── Impact Analysis ──────────────────────────────────────


@router.post("/{project_id}/domain-model/impact-analysis")
async def analyze_impact(
    project_id: uuid.UUID,
    body: ImpactAnalysisRequest,
    db: DbSession,
    user: CurrentUser,
):
    """分析领域模型变更对进行中需求的影响。"""
    todo_repo = TodoRepository(db)
    artifact_repo = ArtifactRepoImpl(db)
    analyzer = ImpactAnalyzer(todo_repo, artifact_repo)

    try:
        scope = ModelChangeScope(body.change_scope)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid scope: {body.change_scope}")

    report = await analyzer.analyze(project_id, body.affected_aggregates, scope)

    return ImpactReportResponse(
        project_id=str(project_id),
        affected_aggregates=list(report.affected_aggregates),
        change_scope=report.change_scope.value,
        max_risk=report.max_risk.name.lower(),
        blocked_count=report.blocked_count,
        summary=report.summary,
        items=[
            {
                "todo_id": str(item.todo_id),
                "todo_title": item.todo_title,
                "current_phase": item.current_phase,
                "affected_aggregates": list(item.affected_aggregates),
                "risk": item.risk.name.lower(),
                "recommendation": item.recommendation,
            }
            for item in report.items
        ],
    )


# ── Model Upgrade Execution ──────────────────────────────


@router.post("/{project_id}/domain-model/upgrade")
async def execute_model_upgrade(
    project_id: uuid.UUID,
    body: ModelUpgradeRequest,
    db: DbSession,
    user: CurrentUser,
):
    """执行领域模型升级。"""
    try:
        strategy = UpgradeStrategy(body.strategy)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid strategy: {body.strategy}")

    project_repo = ProjectRepository(db)
    todo_repo = TodoRepository(db)
    artifact_repo = ArtifactRepoImpl(db)
    feedback_repo = ReviewFeedbackRepository(db)

    orchestrator = ModelUpgradeOrchestrator(
        project_repo, todo_repo, artifact_repo, feedback_repo,
    )
    result = await orchestrator.execute(
        project_id=project_id,
        feedback_ids=[uuid.UUID(fid) for fid in body.feedback_ids],
        new_model=body.new_model,
        strategy=strategy,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "success": True,
        "strategy": result.strategy.value,
        "new_model_version": result.new_model_version,
        "suspended_todo_ids": [str(tid) for tid in result.suspended_todo_ids],
        "auto_resumed_todo_ids": [str(tid) for tid in result.auto_resumed_todo_ids],
        "deferred_feedback_ids": [str(fid) for fid in result.deferred_feedback_ids],
    }


@router.post("/{project_id}/todos/{todo_id}/resume")
async def resume_suspended_todo(
    project_id: uuid.UUID,
    todo_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """手动恢复被暂停的需求。"""
    todo_repo = TodoRepository(db)
    todo = await todo_repo.get_by_id(todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo 不存在")
    if not todo.is_suspended:
        raise HTTPException(status_code=400, detail="该需求未处于暂停状态")

    todo.resume_after_upgrade()
    await todo_repo.update(todo)
    return {"ok": True, "todo_id": str(todo_id), "status": todo.status.value}


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

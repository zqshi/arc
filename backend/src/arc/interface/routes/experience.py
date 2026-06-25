from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from arc.infrastructure.repositories.experience import ExperienceRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas import (
    CreateExperienceRequest,
    ExperienceFeedbackRequest,
    ExperienceListResponse,
    ExperienceResponse,
    UpdateExperienceRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=ExperienceListResponse)
async def search_experiences(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(..., min_length=1),
    project_id: str | None = None,
):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    pid = UUID(project_id) if project_id else None
    results = await svc.search_similar(q, limit=5, project_id=pid, user_id=user.id)
    return ExperienceListResponse(
        items=[_to_response(e) for e in results],
        total=len(results),
    )


@router.get("", response_model=ExperienceListResponse)
async def list_experiences(
    db: DbSession,
    user: CurrentUser,
    project_id: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    from arc.domain.todo.value_objects import ExperienceStatus

    repo = ExperienceRepository(db)
    pid = UUID(project_id) if project_id else None
    st = (
        ExperienceStatus(status)
        if status and status in ("draft", "confirmed", "archived")
        else None
    )
    offset = (page - 1) * page_size

    experiences, total = await repo.list_all(
        project_id=pid, status=st, user_id=user.id, offset=offset, limit=page_size
    )

    if scope and scope in ("personal", "project"):
        experiences = [e for e in experiences if e.scope.value == scope]

    return ExperienceListResponse(
        items=[_to_response(e) for e in experiences],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/analytics/reuse")
async def reuse_analytics(
    db: DbSession,
    user: CurrentUser,
    project_id: str | None = None,
):
    repo = ExperienceRepository(db)
    pid = UUID(project_id) if project_id else None
    data = await repo.get_reuse_analytics(project_id=pid, user_id=user.id)
    return {
        "by_category": data["by_category"],
        "top_reused": [_to_response(e) for e in data["top_reused"]],
        "stale_count": data["stale_count"],
    }


@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience(experience_id: str, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    return _to_response(exp)


@router.post("", response_model=ExperienceResponse, status_code=201)
async def create_experience(req: CreateExperienceRequest, db: DbSession, user: CurrentUser):
    from arc.application.experience.service import ExperienceService
    from arc.domain.todo.value_objects import Tag

    svc = ExperienceService(db)
    created = await svc.create(
        title=req.title,
        scope=req.scope,
        problem=req.problem,
        solution=req.solution,
        decisions=req.decisions,
        pitfalls=req.pitfalls,
        applicable_scenarios=req.applicable_scenarios,
        tags=[Tag(label=t.label, color=t.color) for t in req.tags],
        user_id=user.id,
    )
    return _to_response(created)


@router.patch("/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: str, req: UpdateExperienceRequest, db: DbSession, user: CurrentUser
):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        updated = await svc.update(
            UUID(experience_id), req.model_dump(exclude_unset=True), user_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(updated)


@router.post("/{experience_id}/confirm", response_model=ExperienceResponse)
async def confirm_experience(experience_id: str, db: DbSession, user: CurrentUser):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        exp = await svc.confirm(UUID(experience_id), user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(exp)


@router.post("/{experience_id}/archive", response_model=ExperienceResponse)
async def archive_experience(experience_id: str, db: DbSession, user: CurrentUser):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        exp = await svc.archive(UUID(experience_id), user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(exp)


@router.post("/{experience_id}/promote", response_model=ExperienceResponse)
async def promote_experience(experience_id: str, db: DbSession, user: CurrentUser):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        exp = await svc.promote(UUID(experience_id), user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _to_response(exp)


@router.post("/{experience_id}/distill", response_model=ExperienceResponse)
async def distill_experience(experience_id: str, db: DbSession, user: CurrentUser):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        personal = await svc.distill_to_personal(UUID(experience_id), user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _to_response(personal)


@router.post("/{experience_id}/feedback", status_code=204)
async def feedback_experience(
    experience_id: str, req: ExperienceFeedbackRequest, db: DbSession, user: CurrentUser
):
    from arc.application.experience.service import ExperienceService

    svc = ExperienceService(db)
    try:
        await svc.submit_feedback(
            UUID(experience_id), UUID(req.todo_id), req.helpful, user_id=user.id,
        )
    except ValueError as e:
        detail = str(e)
        code = 409 if "already" in detail.lower() else 404
        raise HTTPException(status_code=code, detail=detail)


@router.post("/{experience_id}/promote-global")
async def promote_to_global(
    experience_id: str, db: DbSession, user: CurrentUser
):
    """T6: 将高质量经验提升为全局经验（跨项目共享）。"""
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id))
    if not exp:
        raise HTTPException(status_code=404, detail="经验不存在")

    try:
        exp.promote_to_global()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await repo.update(exp)
    await db.commit()
    return _to_response(exp)


def _to_response(exp) -> ExperienceResponse:
    return ExperienceResponse(
        id=str(exp.id),
        todo_id=str(exp.todo_id) if exp.todo_id else None,
        project_id=str(exp.project_id) if exp.project_id else None,
        source_experience_id=str(exp.source_experience_id) if exp.source_experience_id else None,
        title=exp.title,
        scope=exp.scope.value if hasattr(exp.scope, "value") else str(exp.scope),
        status=exp.status.value if hasattr(exp.status, "value") else str(exp.status),
        category=exp.category.value if hasattr(exp.category, "value") else str(exp.category),
        source=exp.source.value if hasattr(exp.source, "value") else str(exp.source),
        problem=exp.problem,
        solution=exp.solution,
        decisions=exp.decisions,
        pitfalls=exp.pitfalls,
        applicable_scenarios=exp.applicable_scenarios,
        tags=[{"label": t.label, "color": t.color} for t in exp.tags],
        confidence=exp.confidence,
        reuse_count=exp.reuse_count,
        half_life_days=exp.half_life_days,
        is_stale=exp.is_stale,
        metadata=exp.metadata,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
    )

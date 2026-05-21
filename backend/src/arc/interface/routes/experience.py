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
    results = await svc.search_similar(q, limit=5, project_id=pid)
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
    from arc.domain.todo.value_objects import ExperienceScope, ExperienceStatus

    repo = ExperienceRepository(db)
    pid = UUID(project_id) if project_id else None
    st = ExperienceStatus(status) if status and status in ("draft", "confirmed", "archived") else None
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


@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience(experience_id: str, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    return _to_response(exp)


@router.post("", response_model=ExperienceResponse, status_code=201)
async def create_experience(req: CreateExperienceRequest, db: DbSession, user: CurrentUser):
    from arc.domain.experience.entity import Experience
    from arc.domain.todo.value_objects import ExperienceScope, Tag

    exp = Experience(
        title=req.title,
        scope=ExperienceScope(req.scope) if req.scope in ("personal", "project") else ExperienceScope.PROJECT,
        problem=req.problem,
        solution=req.solution,
        decisions=req.decisions,
        pitfalls=req.pitfalls,
        applicable_scenarios=req.applicable_scenarios,
        tags=[Tag(label=t.label, color=t.color) for t in req.tags],
    )

    embedding_text = f"{exp.title} {exp.problem} {exp.solution} {exp.applicable_scenarios}"
    try:
        from arc.application.ai.resilience import create_resilient_adapter
        adapter = create_resilient_adapter()
        try:
            exp.embedding = await adapter.embed(embedding_text)
        finally:
            await adapter.close()
    except Exception:
        logger.warning("Failed to generate embedding for new experience, saving without it")

    repo = ExperienceRepository(db)
    created = await repo.create(exp, user_id=user.id)
    return _to_response(created)


@router.patch("/{experience_id}", response_model=ExperienceResponse)
async def update_experience(experience_id: str, req: UpdateExperienceRequest, db: DbSession, user: CurrentUser):
    from arc.domain.todo.value_objects import ExperienceScope

    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    updates = req.model_dump(exclude_unset=True)
    for key, val in updates.items():
        if key == "scope" and val:
            exp.scope = ExperienceScope(val)
        else:
            setattr(exp, key, val)

    embedding_text = f"{exp.title} {exp.problem} {exp.solution} {exp.applicable_scenarios}"
    try:
        from arc.application.ai.resilience import create_resilient_adapter
        adapter = create_resilient_adapter()
        try:
            exp.embedding = await adapter.embed(embedding_text)
        finally:
            await adapter.close()
    except Exception:
        logger.warning("Failed to regenerate embedding for experience %s", experience_id)

    updated = await repo.update(exp)
    return _to_response(updated)


@router.post("/{experience_id}/confirm", response_model=ExperienceResponse)
async def confirm_experience(experience_id: str, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    exp.confirm()
    updated = await repo.update(exp)
    return _to_response(updated)


@router.post("/{experience_id}/archive", response_model=ExperienceResponse)
async def archive_experience(experience_id: str, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    exp.archive()
    updated = await repo.update(exp)
    return _to_response(updated)


@router.post("/{experience_id}/promote", response_model=ExperienceResponse)
async def promote_experience(experience_id: str, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    exp.promote_to_personal()
    updated = await repo.update(exp)
    return _to_response(updated)


@router.post("/{experience_id}/feedback", status_code=204)
async def feedback_experience(experience_id: str, req: ExperienceFeedbackRequest, db: DbSession, user: CurrentUser):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id), user_id=user.id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")

    todo_id = UUID(req.todo_id)
    if await repo.has_feedback(exp.id, todo_id):
        raise HTTPException(status_code=409, detail="Feedback already submitted")

    exp.apply_feedback(req.helpful)
    await repo.update(exp)
    await repo.add_feedback(exp.id, todo_id, req.helpful)


def _to_response(exp) -> ExperienceResponse:
    return ExperienceResponse(
        id=str(exp.id),
        todo_id=str(exp.todo_id) if exp.todo_id else None,
        project_id=str(exp.project_id) if exp.project_id else None,
        title=exp.title,
        scope=exp.scope.value if hasattr(exp.scope, "value") else str(exp.scope),
        status=exp.status.value if hasattr(exp.status, "value") else str(exp.status),
        problem=exp.problem,
        solution=exp.solution,
        decisions=exp.decisions,
        pitfalls=exp.pitfalls,
        applicable_scenarios=exp.applicable_scenarios,
        tags=[{"label": t.label, "color": t.color} for t in exp.tags],
        confidence=exp.confidence,
        reuse_count=exp.reuse_count,
        metadata=exp.metadata,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
    )

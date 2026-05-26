from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.experience import ExperienceListResponse, ExperienceResponse

router = APIRouter()


# ── Project Experiences ──────────────────────────────────


def _exp_resp(exp) -> ExperienceResponse:
    return ExperienceResponse(
        id=str(exp.id),
        todo_id=str(exp.todo_id) if exp.todo_id else None,
        project_id=str(exp.project_id) if exp.project_id else None,
        version_id=str(exp.version_id) if exp.version_id else None,
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


@router.get("/{project_id}/experiences", response_model=ExperienceListResponse)
async def list_project_experiences(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    from arc.domain.todo.value_objects import ExperienceCategory, ExperienceStatus
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    st = (
        ExperienceStatus(status)
        if status and status in ("draft", "confirmed", "archived")
        else None
    )
    cat = None
    if category:
        try:
            cat = ExperienceCategory(category)
        except ValueError:
            pass

    offset = (page - 1) * page_size
    experiences, total = await repo.list_all(
        project_id=project_id, status=st, category=cat,
        user_id=user.id, offset=offset, limit=page_size,
    )
    return ExperienceListResponse(
        items=[_exp_resp(e) for e in experiences],
        total=total,
    )


@router.post("/{project_id}/extract-experiences")
async def extract_project_experiences(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    version_id: uuid.UUID | None = None,
):
    from arc.infrastructure.repositories.experience import ExperienceRepository
    from arc.infrastructure.repositories.todo import TodoRepository
    from arc.application.experience.service import ExperienceService

    todo_repo = TodoRepository(db)
    exp_repo = ExperienceRepository(db)
    exp_svc = ExperienceService(db)

    todos, _ = await todo_repo.list_all(
        project_id=project_id, user_id=user.id, offset=0, limit=500,
    )
    if version_id:
        todos = [t for t in todos if t.version_id == version_id]
    done_todos = [t for t in todos if t.status.value == "done"]

    existing_todo_ids: set[uuid.UUID] = set()
    exps, _ = await exp_repo.list_all(project_id=project_id, user_id=user.id, offset=0, limit=10000)
    for e in exps:
        if e.todo_id:
            existing_todo_ids.add(e.todo_id)

    extracted = 0
    skipped = 0
    failed = 0
    for todo in done_todos:
        if todo.id in existing_todo_ids:
            skipped += 1
            continue
        try:
            result = await exp_svc.extract_from_todo(todo)
            if result:
                extracted += 1
            else:
                skipped += 1
        except Exception:
            failed += 1

    await db.commit()
    return {"extracted": extracted, "skipped": skipped, "failed": failed}


@router.get("/{project_id}/experience-insights")
async def project_experience_insights(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    high = await repo.list_high_confidence(project_id)
    return {
        "suggestions": [
            {
                "id": str(e.id),
                "title": e.title,
                "solution": e.solution,
                "confidence": e.confidence,
                "reuse_count": e.reuse_count,
            }
            for e in high
        ]
    }

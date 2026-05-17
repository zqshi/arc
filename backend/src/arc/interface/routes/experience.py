from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from arc.infrastructure.repositories.experience import ExperienceRepository
from arc.interface.deps import DbSession
from arc.interface.schemas import (
    CreateExperienceRequest,
    ExperienceListResponse,
    ExperienceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=ExperienceListResponse)
async def search_experiences(db: DbSession, q: str = Query(..., min_length=1)):
    """Semantic search for related experiences."""
    from arc.application.experience.service import ExperienceService
    svc = ExperienceService(db)
    results = await svc.search_similar(q, limit=5)
    return ExperienceListResponse(
        items=[_to_response(e) for e in results],
        total=len(results),
    )


@router.get("", response_model=ExperienceListResponse)
async def list_experiences(db: DbSession):
    repo = ExperienceRepository(db)
    experiences = await repo.list_all()
    return ExperienceListResponse(
        items=[_to_response(e) for e in experiences],
        total=len(experiences),
    )


@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience(experience_id: str, db: DbSession):
    repo = ExperienceRepository(db)
    exp = await repo.get_by_id(UUID(experience_id))
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    return _to_response(exp)


@router.post("", response_model=ExperienceResponse, status_code=201)
async def create_experience(req: CreateExperienceRequest, db: DbSession):
    from arc.domain.experience.entity import Experience
    from arc.domain.todo.value_objects import Tag

    from arc.domain.todo.value_objects import ExperienceScope

    exp = Experience(
        title=req.title,
        scope=ExperienceScope(req.scope),
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
    created = await repo.create(exp)
    return _to_response(created)


def _to_response(exp) -> ExperienceResponse:
    return ExperienceResponse(
        id=str(exp.id),
        todo_id=str(exp.todo_id) if exp.todo_id else None,
        title=exp.title,
        scope=exp.scope.value if hasattr(exp.scope, 'value') else str(exp.scope),
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

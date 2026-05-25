from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.pipeline.value_objects import PhaseType
from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.pipeline import (
    ArtifactResponse,
    PhaseResponse,
    PipelineStateResponse,
    RollbackRequest,
    UpdateArtifactRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _verify_todo_ownership(db: AsyncSession, todo_id: str, user_id) -> None:
    todo = await TodoRepository(db).get_by_id(UUID(todo_id), user_id=user_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")


# ---------------------------------------------------------------------------
# Pipeline lifecycle
# ---------------------------------------------------------------------------


@router.get("/{todo_id}/pipeline", response_model=PipelineStateResponse)
async def get_pipeline(todo_id: str, db: DbSession, user: CurrentUser):
    """Get complete pipeline state for a todo."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    svc = PipelineService(db)
    state = await svc.get_pipeline_state(UUID(todo_id))

    from arc.infrastructure.repositories.artifact import ArtifactRepository
    from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository

    phases = await PipelinePhaseRepository(db).list_by_todo_id(UUID(todo_id))
    artifacts = await ArtifactRepository(db).list_by_todo_id(UUID(todo_id))

    return PipelineStateResponse(
        todo_id=todo_id,
        current_phase=state["current_phase"],
        phases=[_phase_response(p) for p in phases],
        artifacts=[_artifact_response(a) for a in artifacts],
    )


@router.post("/{todo_id}/pipeline/start", response_model=list[PhaseResponse])
async def start_pipeline(todo_id: str, db: DbSession, user: CurrentUser):
    """Initialize pipeline with all 7 phases and activate the first one."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    svc = PipelineService(db)
    try:
        phases = await svc.initialize_pipeline(UUID(todo_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [_phase_response(p) for p in phases]


# ---------------------------------------------------------------------------
# Phase operations
# ---------------------------------------------------------------------------


@router.post("/{todo_id}/phases/{phase_type}/start", response_model=PhaseResponse)
async def start_phase(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Start a specific phase (create conversation)."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    pt = _parse_phase_type(phase_type)
    svc = PipelineService(db)
    try:
        phase = await svc.start_phase(UUID(todo_id), pt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _phase_response(phase)


@router.post("/{todo_id}/phases/{phase_type}/generate", response_model=ArtifactResponse)
async def generate_artifact(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """AI generates artifact from current phase conversation."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    pt = _parse_phase_type(phase_type)
    svc = PipelineService(db)
    artifact = await svc.generate_artifact(UUID(todo_id), pt)
    if not artifact:
        raise HTTPException(status_code=422, detail="Failed to generate artifact")
    return _artifact_response(artifact)


@router.post("/{todo_id}/phases/{phase_type}/confirm", response_model=PhaseResponse)
async def confirm_phase(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Confirm phase artifact and advance to next phase."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.gate import PhaseGateError
    from arc.application.pipeline.service import PipelineService

    pt = _parse_phase_type(phase_type)
    svc = PipelineService(db)
    try:
        phase = await svc.confirm_phase(UUID(todo_id), pt)
    except PhaseGateError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "type": "gate_failed",
                "gate": exc.result.to_dict(),
            },
        )
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    return _phase_response(phase)


@router.post("/{todo_id}/phases/{phase_type}/skip", response_model=PhaseResponse)
async def skip_phase(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Skip a phase."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    pt = _parse_phase_type(phase_type)
    svc = PipelineService(db)
    try:
        phase = await svc.skip_phase(UUID(todo_id), pt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not phase:
        raise HTTPException(status_code=404, detail="Phase not found")
    return _phase_response(phase)


@router.post("/{todo_id}/pipeline/rollback")
async def rollback_pipeline(todo_id: str, req: RollbackRequest, db: DbSession, user: CurrentUser):
    """Rollback to a previous phase."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.pipeline.service import PipelineService

    pt = _parse_phase_type(req.target_phase)
    svc = PipelineService(db)
    phase = await svc.rollback_to(UUID(todo_id), pt)
    if not phase:
        raise HTTPException(status_code=404, detail="Target phase not found")
    return _phase_response(phase)


# ---------------------------------------------------------------------------
# Artifact operations
# ---------------------------------------------------------------------------


@router.get("/{todo_id}/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(todo_id: str, db: DbSession, user: CurrentUser):
    """List all artifacts for a todo."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.infrastructure.repositories.artifact import ArtifactRepository

    repo = ArtifactRepository(db)
    artifacts = await repo.list_by_todo_id(UUID(todo_id))
    return [_artifact_response(a) for a in artifacts]


@router.get("/{todo_id}/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(todo_id: str, artifact_id: str, db: DbSession, user: CurrentUser):
    """Get a single artifact."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.infrastructure.repositories.artifact import ArtifactRepository

    repo = ArtifactRepository(db)
    artifact = await repo.get_by_id(UUID(artifact_id))
    if not artifact or str(artifact.todo_id) != todo_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_response(artifact)


@router.put("/{todo_id}/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    todo_id: str, artifact_id: str, req: UpdateArtifactRequest, db: DbSession, user: CurrentUser
):
    """Edit artifact content (increments version, unconfirms)."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.artifact.service import ArtifactService

    svc = ArtifactService(db)
    artifact = await svc.update_content(UUID(artifact_id), req.content)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_response(artifact)


@router.post("/{todo_id}/artifacts/{artifact_id}/confirm", response_model=ArtifactResponse)
async def confirm_artifact(todo_id: str, artifact_id: str, db: DbSession, user: CurrentUser):
    """Confirm an artifact."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.artifact.service import ArtifactService

    svc = ArtifactService(db)
    artifact = await svc.confirm(UUID(artifact_id))
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_response(artifact)


@router.post("/{todo_id}/artifacts/{artifact_id}/publish")
async def publish_artifact(todo_id: str, artifact_id: str, db: DbSession, user: CurrentUser):
    """Publish a prototype artifact to object storage and return its public URL."""
    await _verify_todo_ownership(db, todo_id, user.id)

    from arc.application.artifact.publish_service import PublishService

    svc = PublishService(db)
    try:
        url = await svc.publish_prototype(UUID(artifact_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"preview_url": url}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_phase_type(value: str) -> PhaseType:
    try:
        return PhaseType(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase type: {value}")


def _phase_response(phase) -> PhaseResponse:
    return PhaseResponse(
        id=str(phase.id),
        todo_id=str(phase.todo_id),
        phase_type=phase.phase_type.value
        if hasattr(phase.phase_type, "value")
        else phase.phase_type,
        status=phase.status.value if hasattr(phase.status, "value") else phase.status,
        conversation_id=str(phase.conversation_id) if phase.conversation_id else None,
        created_at=phase.created_at,
        updated_at=phase.updated_at,
    )


def _artifact_response(artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=str(artifact.id),
        todo_id=str(artifact.todo_id),
        phase_id=str(artifact.phase_id),
        artifact_type=artifact.artifact_type.value
        if hasattr(artifact.artifact_type, "value")
        else artifact.artifact_type,
        content=artifact.content,
        version=artifact.version,
        is_confirmed=artifact.is_confirmed,
        confirmed_at=artifact.confirmed_at,
        preview_url=artifact.preview_url,
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )

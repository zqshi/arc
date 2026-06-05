from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from arc.infrastructure.models.project import ProjectModel
from arc.infrastructure.repositories.project import (
    ProjectRepository,
    VersionRepository,
)
from arc.interface.deps import CurrentUser, DbSession

router = APIRouter()


# ── Domain Model ────────────────────────────────────────────


@router.get("/{project_id}/domain-model")
async def get_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    return await svc.get_domain_model(project, user.id)


@router.post("/{project_id}/domain-model/refresh")
async def refresh_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    merged, dm = await svc.refresh_domain_model(project, user.id)
    return {"merged": merged, "domain_model": dm}


@router.post("/{project_id}/domain-model/extract-from-code")
async def extract_domain_model_from_code(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Extract domain model directly from codebase source files."""
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    try:
        dm = await svc.extract_from_code(project)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    return {"domain_model": dm}


@router.post("/{project_id}/domain-model/validate")
async def validate_domain_model_route(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    dm = project.domain_model or {}

    from arc.application.review.service import ReviewService
    from arc.infrastructure.repositories.review import ReviewFeedbackRepository

    feedback_repo = ReviewFeedbackRepository(db)
    svc = ReviewService(feedback_repo)
    feedbacks, result = await svc.validate_and_persist(project_id, dm)

    result["feedbacks_created"] = len(feedbacks)
    result["reviewed_model_version"] = dm.get("version", 0)
    return result


@router.put("/{project_id}/domain-model")
async def update_domain_model(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.domain_model = body
    project.updated_at = datetime.now(UTC)
    await repo.update(project)
    return project.domain_model


# ── Mode Switch & Delete ──────────────────────────────────


@router.get("/{project_id}/mode-switch-impact")
async def mode_switch_impact(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.todo import TodoRepository

    repo = TodoRepository(db)
    active_todos, _ = await repo.list_all(project_id=project_id, user_id=user.id, limit=1000)
    active_count = sum(1 for t in active_todos if t.status.value == "active")
    pending_count = sum(1 for t in active_todos if t.status.value == "pending")
    return {
        "active_count": active_count,
        "pending_count": pending_count,
        "safe_to_switch": active_count == 0,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    project.soft_delete()
    await repo.update(project)
    await db.commit()


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """恢复逻辑删除的项目。"""
    repo = ProjectRepository(db)
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    model = result.scalar_one_or_none()
    if not model or model.status != "deleted":
        raise HTTPException(404, "Deleted project not found")
    project = repo._to_entity(model)
    project.restore()
    await repo.update(project)
    await db.commit()
    from arc.interface.routes.project._helpers import _project_resp
    return _project_resp(project)

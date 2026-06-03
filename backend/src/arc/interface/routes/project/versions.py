from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.application.project.service import VersionService
from arc.infrastructure.repositories.project import VersionRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.routes.project._helpers import _version_resp
from arc.interface.schemas.project import (
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)

router = APIRouter()


# ── Versions ──────────────────────────────────────────────


@router.get("/{project_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    repo = VersionRepository(db)
    skip = (page - 1) * page_size
    versions = await repo.list_by_project(project_id, skip=skip, limit=page_size)
    all_stats = await repo.batch_count_todos_by_status([v.id for v in versions])

    # 查询哪些版本有分析结果
    analysis_set: set[uuid.UUID] = set()
    try:
        from sqlalchemy import select
        from arc.infrastructure.models.planning import VersionAnalysisModel
        version_ids = [v.id for v in versions]
        if version_ids:
            result = await db.execute(
                select(VersionAnalysisModel.version_id)
                .where(VersionAnalysisModel.version_id.in_(version_ids))
                .distinct()
            )
            analysis_set = set(result.scalars().all())
    except Exception:
        pass  # 表不存在时跳过

    return [
        _version_resp(v, all_stats.get(v.id, {}), has_analysis=v.id in analysis_set)
        for v in versions
    ]


@router.post("/{project_id}/versions", response_model=VersionResponse, status_code=201)
async def create_version(
    project_id: uuid.UUID,
    body: VersionCreate,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        version = await svc.create_version(
            project_id,
            name=body.name,
            goal=body.goal,
            version_type=body.version_type,
            parent_version_id=uuid.UUID(body.parent_version_id) if body.parent_version_id else None,
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
    stats = await svc.version_repo.count_todos_by_status(version.id)
    return _version_resp(version, stats)


@router.patch("/{project_id}/versions/{version_id}", response_model=VersionResponse)
async def update_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    body: VersionUpdate,
    db: DbSession,
    user: CurrentUser,
):
    repo = VersionRepository(db)
    version = await repo.get_by_id(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(404, "Version not found")

    updates = body.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(version, key, val)
    await repo.update(version)
    stats = await repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/activate",
    response_model=VersionResponse,
)
async def activate_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        version = await svc.activate_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    stats = await svc.version_repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/release",
    response_model=VersionResponse,
)
async def release_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        version, carry_over = await svc.release_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))

    try:
        from arc.application.planning.planning_service import PlanningService

        planning_svc = PlanningService(db)
        await planning_svc.extract_release_experience(project_id, version_id)
    except Exception:
        pass

    stats = await svc.version_repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.delete(
    "/{project_id}/versions/{version_id}",
    status_code=204,
)
async def delete_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        await svc.delete_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))

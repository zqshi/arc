from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.project.service import VersionService
from arc.domain.project.entity import Project, Version
from arc.infrastructure.repositories.project import (
    ProjectRepository,
    VersionRepository,
)
from arc.interface.deps import get_db
from arc.interface.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)
from arc.interface.schemas.experience import ExperienceListResponse, ExperienceResponse

import re

router = APIRouter()


def _next_version_name(existing_versions: list[Version], version_type: str) -> str:
    latest = (0, 0, 0)
    for v in existing_versions:
        m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", v.name)
        if m:
            parsed = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            if parsed > latest:
                latest = parsed

    major, minor, patch = latest
    if major == 0 and minor == 0 and patch == 0:
        if version_type == "major":
            return "v1.0"
        return "v0.1"

    if version_type == "major":
        return f"v{major + 1}.0"
    if version_type == "minor":
        return f"v{major}.{minor + 1}"
    return f"v{major}.{minor}.{patch + 1}"


def _project_resp(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        tech_stack=p.tech_stack,
        repo_url=p.repo_url,
        conventions=p.conventions,
        status=p.status.value,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


def _version_resp(v: Version, todo_stats: dict[str, int] | None = None) -> VersionResponse:
    stats = None
    if todo_stats is not None:
        stats = {
            "pending": todo_stats.get("pending", 0),
            "active": todo_stats.get("active", 0),
            "done": todo_stats.get("done", 0),
            "error": todo_stats.get("error", 0),
            "total": sum(todo_stats.values()),
        }
    return VersionResponse(
        id=str(v.id),
        project_id=str(v.project_id),
        name=v.name,
        goal=v.goal,
        status=v.status.value,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        order=v.order,
        changelog=v.changelog,
        todo_stats=stats,
        created_at=v.created_at.isoformat(),
        updated_at=v.updated_at.isoformat(),
    )


# ── Projects ──────────────────────────────────────────────


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    include_archived: bool = False,
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    projects = await repo.list_all(include_archived=include_archived)
    return [_project_resp(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        name=body.name,
        description=body.description,
        tech_stack=body.tech_stack,
        repo_url=body.repo_url,
        conventions=body.conventions,
    )
    repo = ProjectRepository(db)
    await repo.create(project)
    await db.commit()
    return _project_resp(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _project_resp(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    updates = body.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(project, key, val)
    await repo.update(project)
    await db.commit()
    return _project_resp(project)


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.archive()
    await repo.update(project)
    await db.commit()
    return _project_resp(project)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    version_repo = VersionRepository(db)
    count = await version_repo.count_by_project(project_id)
    if count > 0:
        raise HTTPException(409, "请先删除所有版本后再删除项目")
    await repo.delete(project_id)
    await db.commit()


# ── Versions ──────────────────────────────────────────────


@router.get("/{project_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = VersionRepository(db)
    versions = await repo.list_by_project(project_id)
    results = []
    for v in versions:
        stats = await repo.count_todos_by_status(v.id)
        results.append(_version_resp(v, stats))
    return results


@router.post(
    "/{project_id}/versions", response_model=VersionResponse, status_code=201
)
async def create_version(
    project_id: uuid.UUID,
    body: VersionCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = VersionRepository(db)
    next_order = await repo._next_order(project_id)

    if body.name and body.name.strip():
        name = body.name.strip()
    else:
        all_versions = await repo.list_by_project(project_id)
        name = _next_version_name(all_versions, body.version_type)

    version = Version(
        project_id=project_id,
        name=name,
        goal=body.goal,
        order=next_order,
        parent_version_id=uuid.UUID(body.parent_version_id) if body.parent_version_id else None,
    )
    try:
        await repo.create(version)
    except ValueError as e:
        raise HTTPException(409, str(e))
    await db.commit()
    stats = await repo.count_todos_by_status(version.id)
    return _version_resp(version, stats)


@router.patch(
    "/{project_id}/versions/{version_id}", response_model=VersionResponse
)
async def update_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    body: VersionUpdate,
    db: AsyncSession = Depends(get_db),
):
    repo = VersionRepository(db)
    version = await repo.get_by_id(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(404, "Version not found")

    updates = body.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(version, key, val)
    await repo.update(version)
    await db.commit()
    stats = await repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/activate",
    response_model=VersionResponse,
)
async def activate_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    try:
        version = await svc.activate_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    await db.commit()
    stats = await svc.version_repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/release",
    response_model=VersionResponse,
)
async def release_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    svc = VersionService(db)
    try:
        version, carry_over = await svc.release_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    await db.commit()
    stats = await svc.version_repo.count_todos_by_status(version_id)
    resp = _version_resp(version, stats)
    return resp


@router.delete(
    "/{project_id}/versions/{version_id}",
    status_code=204,
)
async def delete_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    repo = VersionRepository(db)
    version = await repo.get_by_id(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(404, "Version not found")
    if version.status.value == "released":
        raise HTTPException(409, "已发布版本不可删除")
    stats = await repo.count_todos_by_status(version_id)
    if sum(stats.values()) > 0:
        raise HTTPException(409, "请先删除版本下的需求后再删除版本")
    await repo.delete(version_id)
    await db.commit()


# ── Project Experiences ──────────────────────────────────


@router.get("/{project_id}/experiences", response_model=ExperienceListResponse)
async def list_project_experiences(
    project_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    from arc.domain.todo.value_objects import ExperienceStatus
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    st = ExperienceStatus(status) if status and status in ("draft", "confirmed", "archived") else None
    experiences = await repo.list_all(project_id=project_id, status=st)

    return ExperienceListResponse(
        items=[_exp_resp(e) for e in experiences],
        total=len(experiences),
    )


@router.get("/{project_id}/experience-insights")
async def project_experience_insights(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
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


def _exp_resp(exp) -> ExperienceResponse:
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

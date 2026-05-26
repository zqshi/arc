from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

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
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    dm = project.domain_model
    if not dm or (not dm.get("aggregates") and not dm.get("subdomains")):
        from arc.application.execution.domain_model_extractor import DomainModelExtractor
        from arc.infrastructure.repositories.artifact import ArtifactRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        todo_repo = TodoRepository(db)
        art_repo = ArtifactRepository(db)
        todos, _ = await todo_repo.list_all(project_id=project_id, user_id=user.id, offset=0, limit=100)
        for todo in todos:
            arts = await art_repo.list_by_todo_id(todo.id)
            for art in arts:
                if art.artifact_type.value == "tech_architecture" and (
                    art.content.get("data_model", {}).get("entities")
                    or art.content.get("domain_design")
                ):
                    extractor = DomainModelExtractor(db)
                    updated = await extractor.extract_and_merge(todo.id, art.content)
                    if updated:
                        await db.commit()
                        project = await repo.get_by_id(project_id, user_id=user.id)
                        dm = project.domain_model
                        break
            if dm and (dm.get("aggregates") or dm.get("subdomains")):
                break

    return dm or {
        "subdomains": [],
        "contexts": [],
        "aggregates": [],
        "relations": [],
        "aggregate_relations": [],
    }


@router.post("/{project_id}/domain-model/refresh")
async def refresh_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.execution.domain_model_extractor import DomainModelExtractor
    from arc.infrastructure.repositories.artifact import ArtifactRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    todo_repo = TodoRepository(db)
    art_repo = ArtifactRepository(db)
    extractor = DomainModelExtractor(db)

    todos, _ = await todo_repo.list_all(project_id=project_id, user_id=user.id, offset=0, limit=500)
    merged = 0
    for todo in todos:
        arts = await art_repo.list_by_todo_id(todo.id)
        for art in arts:
            if art.artifact_type.value != "tech_architecture":
                continue
            if not (art.content.get("data_model", {}).get("entities") or art.content.get("domain_design")):
                continue
            updated = await extractor.extract_and_merge(todo.id, art.content)
            if updated:
                merged += 1

    await db.commit()
    project = await repo.get_by_id(project_id, user_id=user.id)
    dm = project.domain_model or {
        "subdomains": [], "contexts": [], "aggregates": [],
        "relations": [], "aggregate_relations": [],
    }
    return {"merged": merged, "domain_model": dm}


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
    version_repo = VersionRepository(db)
    count = await version_repo.count_by_project(project_id)
    if count > 0:
        raise HTTPException(409, "请先删除所有版本后再删除项目")

    from arc.infrastructure.storage import get_storage
    storage = get_storage()
    await storage.async_delete_prefix(f"documents/{project_id}")

    await repo.delete(project_id)

"""Todo route helpers — shared utilities for todo route submodules."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.todo.entity import Todo
from arc.interface.schemas import TodoResponse
from arc.infrastructure.models.project import ProjectModel, VersionModel


def to_response(
    todo: Todo,
    *,
    project_name: str | None = None,
    version_name: str | None = None,
    blocked_by: list[uuid.UUID] | None = None,
    blocks: list[uuid.UUID] | None = None,
) -> TodoResponse:
    needs_attention = todo.status.value in ("active", "error") and (
        todo.last_seen_at is None or todo.updated_at > todo.last_seen_at
    )
    return TodoResponse(
        id=str(todo.id),
        title=todo.title,
        description=todo.description,
        status=todo.status.value,
        project_id=str(todo.project_id) if todo.project_id else None,
        version_id=str(todo.version_id) if todo.version_id else None,
        project_name=project_name,
        version_name=version_name,
        priority=todo.priority,
        current_phase=todo.current_phase.value if todo.current_phase else None,
        execution_mode=todo.execution_mode.value,
        needs_attention=needs_attention,
        tags=[{"label": t.label, "color": t.color} for t in todo.tags],
        blocked_by=[str(uid) for uid in (blocked_by or [])],
        blocks=[str(uid) for uid in (blocks or [])],
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


async def resolve_names(db: AsyncSession, todos: list[Todo]) -> tuple[dict, dict]:
    proj_ids = {t.project_id for t in todos if t.project_id}
    ver_ids = {t.version_id for t in todos if t.version_id}

    proj_names: dict = {}
    ver_names: dict = {}

    if proj_ids:
        result = await db.execute(
            select(ProjectModel.id, ProjectModel.name).where(ProjectModel.id.in_(proj_ids))
        )
        proj_names = {row[0]: row[1] for row in result.all()}

    if ver_ids:
        result = await db.execute(
            select(VersionModel.id, VersionModel.name).where(VersionModel.id.in_(ver_ids))
        )
        ver_names = {row[0]: row[1] for row in result.all()}

    return proj_names, ver_names

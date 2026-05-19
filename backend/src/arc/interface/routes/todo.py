from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.domain.todo.value_objects import TodoStatus
from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas import (
    ConversationListResponse,
    CreateTodoRequest,
    TodoListResponse,
    TodoResponse,
    UpdateTodoRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=TodoListResponse)
async def list_todos(
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
    project_id: str | None = None,
    version_id: str | None = None,
):
    repo = TodoRepository(db)
    pid = UUID(project_id) if project_id else None
    vid = UUID(version_id) if version_id else None
    if status and status != "all":
        todos = await repo.list_by_status(TodoStatus(status), user_id=user.id)
    else:
        todos = await repo.list_all(project_id=pid, version_id=vid, user_id=user.id)

    proj_names, ver_names = await _resolve_names(db, todos)
    return TodoListResponse(
        items=[_to_response(t, project_name=proj_names.get(t.project_id), version_name=ver_names.get(t.version_id)) for t in todos],
        total=len(todos),
    )


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id))
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    project_name = None
    version_name = None
    if todo.project_id:
        from arc.infrastructure.repositories.project import ProjectRepository
        project = await ProjectRepository(db).get_by_id(todo.project_id)
        if project:
            project_name = project.name
    if todo.version_id:
        from arc.infrastructure.repositories.project import VersionRepository
        version = await VersionRepository(db).get_by_id(todo.version_id)
        if version:
            version_name = version.name

    return _to_response(todo, project_name=project_name, version_name=version_name)


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(req: CreateTodoRequest, db: DbSession, user: CurrentUser):
    from arc.domain.todo.entity import Todo
    from arc.domain.todo.value_objects import Tag

    todo = Todo(
        title=req.title,
        description=req.description,
        project_id=UUID(req.project_id) if req.project_id else None,
        version_id=UUID(req.version_id) if req.version_id else None,
        priority=req.priority,
        tags=[Tag(label=t.label, color=t.color) for t in req.tags],
    )
    repo = TodoRepository(db)
    created = await repo.create(todo, user_id=user.id)
    return _to_response(created)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, req: UpdateTodoRequest, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id))
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if req.title is not None:
        todo.title = req.title
    if req.description is not None:
        todo.description = req.description
    if req.priority is not None:
        todo.priority = req.priority
    if req.project_id is not None:
        todo.project_id = UUID(req.project_id) if req.project_id else None
    if req.version_id is not None:
        todo.version_id = UUID(req.version_id) if req.version_id else None
    if req.tags is not None:
        from arc.domain.todo.value_objects import Tag
        todo.tags = [Tag(label=t.label, color=t.color) for t in req.tags]

    updated = await repo.update(todo)
    return _to_response(updated)


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    await repo.delete(UUID(todo_id))


@router.post("/{todo_id}/extract-tags", response_model=TodoResponse)
async def extract_tags(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.todo.service import TodoService

    svc = TodoService(db)
    todo = await svc.extract_tags(UUID(todo_id))
    return _to_response(todo)


@router.get("/{todo_id}/conversations", response_model=ConversationListResponse)
async def list_todo_conversations(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.interface.routes.conversation import _to_response as conv_to_response
    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_by_todo_id(UUID(todo_id))
    return ConversationListResponse(
        items=[conv_to_response(c) for c in conversations],
        total=len(conversations),
    )


def _to_response(
    todo, *, project_name: str | None = None, version_name: str | None = None,
) -> TodoResponse:
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
        tags=[{"label": t.label, "color": t.color} for t in todo.tags],
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


async def _resolve_names(db, todos) -> tuple[dict, dict]:
    from sqlalchemy import select
    from arc.infrastructure.models.project import ProjectModel, VersionModel

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

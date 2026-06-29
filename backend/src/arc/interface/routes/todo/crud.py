"""Todo CRUD + dependencies routes."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from arc.domain.todo.value_objects import TodoStatus
from arc.infrastructure.repositories.todo import TodoDependencyRepository, TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.routes.todo._helpers import resolve_names, to_response
from arc.interface.schemas import (
    AddDependencyRequest,
    CreateTodoRequest,
    DependencyListResponse,
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
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    repo = TodoRepository(db)
    pid = UUID(project_id) if project_id else None
    vid = UUID(version_id) if version_id else None
    offset = (page - 1) * page_size

    if status and status != "all":
        todos, total = await repo.list_by_status(
            TodoStatus(status), user_id=user.id, offset=offset, limit=page_size
        )
    else:
        todos, total = await repo.list_all(
            project_id=pid, version_id=vid, user_id=user.id, offset=offset, limit=page_size
        )

    proj_names, ver_names, proj_constraints = await resolve_names(db, todos)
    dep_repo = TodoDependencyRepository(db)
    todo_ids = [t.id for t in todos]
    blocked_by_map = await dep_repo.get_map(todo_ids)
    blocks_map = await dep_repo.get_blocks_map(todo_ids)
    return TodoListResponse(
        items=[
            to_response(
                t,
                project_name=proj_names.get(t.project_id),
                version_name=ver_names.get(t.version_id),
                process_constraint=proj_constraints.get(t.project_id),
                blocked_by=blocked_by_map.get(t.id, []),
                blocks=blocks_map.get(t.id, []),
            )
            for t in todos
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    await repo.mark_seen(UUID(todo_id))
    await db.commit()

    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    project_name = None
    version_name = None
    process_constraint = None
    if todo.project_id:
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(db).get_by_id(todo.project_id)
        if project:
            project_name = project.name
            process_constraint = project.process_constraint.value
    if todo.version_id:
        from arc.infrastructure.repositories.project import VersionRepository

        version = await VersionRepository(db).get_by_id(todo.version_id)
        if version:
            version_name = version.name

    dep_repo = TodoDependencyRepository(db)
    blocked_by = await dep_repo.get_blocked_by(UUID(todo_id))
    blocks = await dep_repo.get_blocks(UUID(todo_id))
    return to_response(todo, project_name=project_name, version_name=version_name,
                       process_constraint=process_constraint,
                       blocked_by=blocked_by, blocks=blocks)


@router.get("/{todo_id}/dependencies", response_model=DependencyListResponse)
async def get_dependencies(todo_id: str, db: DbSession, user: CurrentUser):
    dep_repo = TodoDependencyRepository(db)
    blocked_by = await dep_repo.get_blocked_by(UUID(todo_id))
    blocks = await dep_repo.get_blocks(UUID(todo_id))
    return DependencyListResponse(
        blocked_by=[str(x) for x in blocked_by],
        blocks=[str(x) for x in blocks],
    )


@router.post("/{todo_id}/dependencies", status_code=201)
async def add_dependency(todo_id: str, req: AddDependencyRequest, db: DbSession, user: CurrentUser):
    dep_repo = TodoDependencyRepository(db)
    await dep_repo.add(UUID(todo_id), UUID(req.depends_on_id))
    return {"ok": True}


@router.delete("/{todo_id}/dependencies/{depends_on_id}", status_code=204)
async def remove_dependency(todo_id: str, depends_on_id: str, db: DbSession, user: CurrentUser):
    dep_repo = TodoDependencyRepository(db)
    await dep_repo.remove(UUID(todo_id), UUID(depends_on_id))


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(req: CreateTodoRequest, db: DbSession, user: CurrentUser):
    from arc.domain.todo.entity import Todo
    from arc.domain.todo.value_objects import Tag

    tags = [Tag(label=t.label, color=t.color) for t in (req.tags or [])]
    todo = Todo(
        title=req.title,
        description=req.description or "",
        project_id=UUID(req.project_id) if req.project_id else None,
        version_id=UUID(req.version_id) if req.version_id else None,
        priority=req.priority or 2,
        tags=tags,
    )
    repo = TodoRepository(db)
    todo = await repo.create(todo, user_id=user.id)
    return to_response(todo)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, req: UpdateTodoRequest, db: DbSession, user: CurrentUser):
    from arc.domain.todo.value_objects import Tag

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if req.title is not None:
        todo.title = req.title
    if req.description is not None:
        todo.description = req.description
    if req.priority is not None:
        todo.priority = req.priority
    if req.version_id is not None:
        todo.version_id = UUID(req.version_id) if req.version_id else None
    if req.tags is not None:
        todo.tags = [Tag(label=t.get("label", ""), color=t.get("color", "#888")) for t in req.tags]

    todo = await repo.update(todo)
    return to_response(todo)


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    await repo.delete(UUID(todo_id), user_id=user.id)


@router.post("/{todo_id}/complete", response_model=TodoResponse)
async def complete_todo(todo_id: str, db: DbSession, user: CurrentUser):
    """手动标记需求为已完成。"""
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    try:
        todo.force_complete()
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    await repo.update(todo)
    return to_response(todo)


@router.post("/{todo_id}/reopen", response_model=TodoResponse)
async def reopen_todo(todo_id: str, db: DbSession, user: CurrentUser):
    """重新打开已完成/异常的需求。"""
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    try:
        todo.reopen()
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

    await repo.update(todo)
    return to_response(todo)

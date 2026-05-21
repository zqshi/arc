from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

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

    proj_names, ver_names = await _resolve_names(db, todos)
    return TodoListResponse(
        items=[_to_response(t, project_name=proj_names.get(t.project_id), version_name=ver_names.get(t.version_id)) for t in todos],
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
    from arc.domain.project.value_objects import ExecutionMode
    from arc.domain.todo.entity import Todo
    from arc.domain.todo.value_objects import Tag
    from arc.infrastructure.repositories.project import ProjectRepository

    execution_mode = ExecutionMode.PIPELINE
    if req.project_id:
        project = await ProjectRepository(db).get_by_id(UUID(req.project_id))
        if project:
            execution_mode = project.execution_mode

    todo = Todo(
        title=req.title,
        description=req.description,
        project_id=UUID(req.project_id) if req.project_id else None,
        version_id=UUID(req.version_id) if req.version_id else None,
        priority=req.priority,
        tags=[Tag(label=t.label, color=t.color) for t in req.tags],
        execution_mode=execution_mode,
    )
    repo = TodoRepository(db)
    created = await repo.create(todo, user_id=user.id)
    return _to_response(created)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, req: UpdateTodoRequest, db: DbSession, user: CurrentUser):
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
    await repo.delete(UUID(todo_id), user_id=user.id)


@router.post("/{todo_id}/extract-tags", response_model=TodoResponse)
async def extract_tags(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.todo.service import TodoService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    svc = TodoService(db)
    todo = await svc.extract_tags(UUID(todo_id))
    return _to_response(todo)


@router.get("/{todo_id}/conversations", response_model=ConversationListResponse)
async def list_todo_conversations(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.interface.routes.conversation import _to_response as conv_to_response

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_by_todo_id(UUID(todo_id))
    return ConversationListResponse(
        items=[conv_to_response(c) for c in conversations],
        total=len(conversations),
    )


@router.post("/{todo_id}/start-conversation", response_model=TodoResponse)
async def start_conversation(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.execution.conversation_strategy import ConversationExecutionService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if todo.execution_mode.value != "conversation":
        raise HTTPException(status_code=400, detail="此需求不是对话模式")

    svc = ConversationExecutionService(db)
    _, _ = await svc.initialize(UUID(todo_id))
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    return _to_response(todo)


@router.get("/{todo_id}/deliverables")
async def get_deliverables(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.execution.conversation_strategy import ConversationExecutionService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    svc = ConversationExecutionService(db)
    state = await svc.get_tracker_state(UUID(todo_id))
    return state


@router.post("/{todo_id}/quick-message")
async def send_quick_message(todo_id: str, db: DbSession, user: CurrentUser, body: dict):
    import asyncio

    from arc.application.project.task_stream import project_task_stream
    from arc.domain.todo.value_objects import MessageRole
    from arc.infrastructure.repositories.conversation import ConversationRepository

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_by_todo_id(UUID(todo_id))
    conv = next((c for c in conversations if c.purpose.value == "unified"), None)
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation for this todo")

    user_msg = conv.add_message(role=MessageRole.USER, content=content)
    await conv_repo.add_message(conv.id, user_msg)
    await db.commit()

    project_id = str(todo.project_id) if todo.project_id else None

    async def _run_ai():
        from arc.application.execution.conversation_strategy import ConversationExecutionService
        from arc.infrastructure.database import async_session_factory

        async with async_session_factory() as _db:
            _conv_repo = ConversationRepository(_db)
            _conv = await _conv_repo.get_by_id(conv.id)
            if not _conv:
                return
            svc = ConversationExecutionService(_db)
            ai_msg_id = None
            try:
                async for chunk in svc.generate_response_stream(_conv):
                    event_type = chunk.get("event")
                    if event_type == "artifacts_extracted":
                        if project_id:
                            await project_task_stream.emit(project_id, {
                                "event": "task_done",
                                "todo_id": todo_id,
                                "artifacts": chunk.get("artifact_names", []),
                            })
                        continue

                    if ai_msg_id is None:
                        ai_msg_id = chunk.get("message_id")
                        if project_id:
                            await project_task_stream.emit(project_id, {
                                "event": "task_status",
                                "todo_id": todo_id,
                                "status": "running",
                                "stage": "AI 正在生成回复...",
                            })

                    if project_id:
                        await project_task_stream.emit(project_id, {
                            "event": "task_chunk",
                            "todo_id": todo_id,
                            "content": chunk.get("content", ""),
                        })
            except Exception as exc:
                logger.error("quick-message AI failed: %s", exc, exc_info=True)
                if project_id:
                    await project_task_stream.emit(project_id, {
                        "event": "task_status",
                        "todo_id": todo_id,
                        "status": "error",
                        "stage": "AI响应生成失败",
                    })
            finally:
                if project_id:
                    await project_task_stream.emit(project_id, {
                        "event": "task_status",
                        "todo_id": todo_id,
                        "status": "idle",
                        "stage": "等待用户输入",
                    })
                await _db.commit()

    asyncio.create_task(_run_ai())

    return {
        "message_id": str(user_msg.id),
        "status": "accepted",
    }


def _to_response(
    todo, *, project_name: str | None = None, version_name: str | None = None,
) -> TodoResponse:
    needs_attention = (
        todo.status.value in ("active", "error")
        and (todo.last_seen_at is None or todo.updated_at > todo.last_seen_at)
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

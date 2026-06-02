"""Todo conversations, deliverables, and quick messages."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.routes.todo._helpers import to_response
from arc.interface.schemas import ConversationListResponse, TodoResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{todo_id}/extract-tags", response_model=TodoResponse)
async def extract_tags(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.todo.service import TodoService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    svc = TodoService(db)
    todo = await svc.extract_tags(UUID(todo_id))
    return to_response(todo)


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
    return to_response(todo)


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
    from arc.application.todo.quick_message_service import run_ai_response
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

    def _on_ai_done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception():
            logger.error("Background AI task failed: %s", t.exception())

    task = asyncio.create_task(
        run_ai_response(
            conversation_id=conv.id,
            todo_id=todo_id,
            project_id=project_id,
        )
    )
    task.add_done_callback(_on_ai_done)

    return {
        "message_id": str(user_msg.id),
        "status": "accepted",
    }

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas import (
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
)

router = APIRouter()


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, db: DbSession, user: CurrentUser):
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(UUID(conversation_id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    todo = await TodoRepository(db).get_by_id(conv.todo_id, user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _to_response(conv)


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str, req: SendMessageRequest, db: DbSession, user: CurrentUser
):
    """Send a user message and trigger AI response (non-streaming)."""
    repo = ConversationRepository(db)
    conv = await repo.get_by_id(UUID(conversation_id))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    todo = await TodoRepository(db).get_by_id(conv.todo_id, user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    from arc.domain.todo.value_objects import MessageRole

    message = conv.add_message(role=MessageRole.USER, content=req.content)
    await repo.add_message(conv.id, message)

    # Trigger AI response asynchronously
    from arc.application.conversation.service import ConversationService

    ai_service = ConversationService(db)
    ai_message = await ai_service.generate_response(conv)
    await repo.add_message(conv.id, ai_message)

    return MessageResponse(
        id=str(ai_message.id),
        conversation_id=str(ai_message.conversation_id),
        role=ai_message.role.value,
        content=ai_message.content,
        metadata=ai_message.metadata,
        created_at=ai_message.created_at,
    )


def _to_response(conv) -> ConversationResponse:
    return ConversationResponse(
        id=str(conv.id),
        todo_id=str(conv.todo_id),
        purpose=conv.purpose.value,
        messages=[
            MessageResponse(
                id=str(m.id),
                conversation_id=str(m.conversation_id),
                role=m.role.value,
                content=m.content,
                metadata=m.metadata,
                created_at=m.created_at,
            )
            for m in conv.messages
        ],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )

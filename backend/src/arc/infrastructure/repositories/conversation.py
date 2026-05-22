from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.conversation.entity import Conversation as ConvEntity
from arc.domain.conversation.entity import Message as MsgEntity
from arc.domain.conversation.repository import IConversationRepository
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole
from arc.infrastructure.models.conversation import (
    Conversation as ConvModel,
)
from arc.infrastructure.models.conversation import (
    Message as MsgModel,
)


class ConversationRepository(IConversationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, conv_id: uuid.UUID) -> ConvEntity | None:
        result = await self.db.execute(select(ConvModel).where(ConvModel.id == conv_id))
        row = result.scalar_one_or_none()
        if not row:
            return None
        messages = await self._load_messages(conv_id)
        return self._to_entity(row, messages)

    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[ConvEntity]:
        result = await self.db.execute(
            select(ConvModel)
            .where(ConvModel.todo_id == todo_id)
            .order_by(ConvModel.created_at.desc())
        )
        entities = []
        for row in result.scalars().all():
            messages = await self._load_messages(row.id)
            entities.append(self._to_entity(row, messages))
        return entities

    async def get_by_todo_and_purpose(
        self,
        todo_id: uuid.UUID,
        purpose: ConversationPurpose,
    ) -> ConvEntity | None:
        result = await self.db.execute(
            select(ConvModel).where(
                ConvModel.todo_id == todo_id,
                ConvModel.purpose == purpose.value,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        messages = await self._load_messages(row.id)
        return self._to_entity(row, messages)

    async def create(self, entity: ConvEntity) -> ConvEntity:
        model = ConvModel(
            id=entity.id,
            todo_id=entity.todo_id,
            purpose=entity.purpose.value,
        )
        self.db.add(model)
        await self.db.flush()

        for msg in entity.messages:
            await self._insert_message(msg)

        await self.db.refresh(model)
        return entity

    async def add_message(self, conv_id: uuid.UUID, message: MsgEntity) -> MsgEntity:
        msg_model = MsgModel(
            id=message.id,
            conversation_id=conv_id,
            role=message.role.value,
            content=message.content,
            metadata_=message.metadata or None,
        )
        self.db.add(msg_model)
        await self.db.flush()
        return message

    async def _insert_message(self, message: MsgEntity) -> None:
        msg_model = MsgModel(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role.value,
            content=message.content,
            metadata_=message.metadata or None,
        )
        self.db.add(msg_model)
        await self.db.flush()

    async def _load_messages(self, conv_id: uuid.UUID) -> list[MsgEntity]:
        result = await self.db.execute(
            select(MsgModel)
            .where(MsgModel.conversation_id == conv_id)
            .order_by(MsgModel.created_at.asc())
        )
        return [
            MsgEntity(
                id=m.id,
                conversation_id=m.conversation_id,
                role=MessageRole(m.role),
                content=m.content,
                metadata=m.metadata_ or {},
                created_at=m.created_at,
            )
            for m in result.scalars().all()
        ]

    @staticmethod
    def _to_entity(model: ConvModel, messages: list[MsgEntity]) -> ConvEntity:
        return ConvEntity(
            id=model.id,
            todo_id=model.todo_id,
            purpose=ConversationPurpose(model.purpose),
            messages=messages,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.conversation.entity import Conversation, Message
from arc.domain.todo.value_objects import ConversationPurpose


class AbstractConversationRepository(ABC):
    """Domain-level contract for conversation persistence."""

    @abstractmethod
    async def get_by_id(
        self, conversation_id: uuid.UUID
    ) -> Conversation | None: ...

    @abstractmethod
    async def list_by_todo_id(
        self, todo_id: uuid.UUID
    ) -> list[Conversation]: ...

    @abstractmethod
    async def get_by_todo_and_purpose(
        self,
        todo_id: uuid.UUID,
        purpose: ConversationPurpose,
    ) -> Conversation | None: ...

    @abstractmethod
    async def create(self, entity: Conversation) -> Conversation: ...

    @abstractmethod
    async def add_message(
        self,
        conv_id: uuid.UUID,
        message: Message,
    ) -> Message: ...


# Backward-compatible alias
IConversationRepository = AbstractConversationRepository

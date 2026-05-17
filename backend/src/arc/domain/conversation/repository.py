from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.conversation.entity import Conversation, Message
from arc.domain.todo.value_objects import MessageRole


class IConversationRepository(ABC):
    @abstractmethod
    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None: ...

    @abstractmethod
    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[Conversation]: ...

    @abstractmethod
    async def create(self, conversation: Conversation) -> Conversation: ...

    @abstractmethod
    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: MessageRole,
        content: str,
        metadata: dict | None = None,
    ) -> Message: ...

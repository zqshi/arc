from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.todo.value_objects import ConversationPurpose, MessageRole


@dataclass
class Message:
    role: MessageRole
    content: str
    conversation_id: uuid.UUID
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Conversation:
    todo_id: uuid.UUID
    purpose: ConversationPurpose
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def add_message(
        self,
        role: MessageRole,
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        """Append a new message to this conversation."""
        if not content or not content.strip():
            raise ValueError("Message content cannot be empty")
        msg = Message(
            role=role,
            content=content,
            conversation_id=self.id,
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.updated_at = datetime.now(UTC)
        return msg

    def get_context_window(self, max_messages: int = 50) -> list[Message]:
        """Return the most recent *max_messages* messages for LLM context."""
        if max_messages <= 0:
            raise ValueError("max_messages must be positive")
        return self.messages[-max_messages:]

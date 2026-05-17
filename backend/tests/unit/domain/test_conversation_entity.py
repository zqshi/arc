from __future__ import annotations

import uuid

import pytest

from arc.domain.conversation.entity import Conversation
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole

# ---------------------------------------------------------------------------
# Entity creation
# ---------------------------------------------------------------------------

class TestConversationCreation:
    def test_create_with_defaults(self) -> None:
        todo_id = uuid.uuid4()
        conv = Conversation(todo_id=todo_id, purpose=ConversationPurpose.CLARIFICATION)
        assert conv.todo_id == todo_id
        assert conv.purpose == ConversationPurpose.CLARIFICATION
        assert isinstance(conv.id, uuid.UUID)
        assert conv.messages == []

    def test_create_with_purpose_development(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.DEVELOPMENT)
        assert conv.purpose == ConversationPurpose.DEVELOPMENT


# ---------------------------------------------------------------------------
# add_message
# ---------------------------------------------------------------------------

class TestAddMessage:
    def test_add_single_message(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        msg = conv.add_message(MessageRole.USER, "Hello")
        assert len(conv.messages) == 1
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.conversation_id == conv.id
        assert isinstance(msg.id, uuid.UUID)
        assert msg.metadata == {}

    def test_add_message_with_metadata(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        meta = {"model": "claude-4", "tokens": 150}
        msg = conv.add_message(MessageRole.ASSISTANT, "Hi there", metadata=meta)
        assert msg.metadata == meta

    def test_add_multiple_messages(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        conv.add_message(MessageRole.USER, "Question")
        conv.add_message(MessageRole.ASSISTANT, "Answer")
        conv.add_message(MessageRole.USER, "Follow-up")
        assert len(conv.messages) == 3
        assert conv.messages[0].role == MessageRole.USER
        assert conv.messages[1].role == MessageRole.ASSISTANT
        assert conv.messages[2].role == MessageRole.USER

    def test_add_message_updates_timestamp(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        original = conv.updated_at
        conv.add_message(MessageRole.USER, "msg")
        assert conv.updated_at >= original

    def test_add_empty_message_raises(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        with pytest.raises(ValueError, match="content cannot be empty"):
            conv.add_message(MessageRole.USER, "")
        with pytest.raises(ValueError, match="content cannot be empty"):
            conv.add_message(MessageRole.USER, "   ")

    def test_add_system_message(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.DEVELOPMENT)
        msg = conv.add_message(MessageRole.SYSTEM, "You are a coding assistant.")
        assert msg.role == MessageRole.SYSTEM


# ---------------------------------------------------------------------------
# get_context_window
# ---------------------------------------------------------------------------

class TestContextWindow:
    def _build_conversation(self, n: int) -> Conversation:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        for i in range(n):
            role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            conv.add_message(role, f"Message {i}")
        return conv

    def test_returns_all_when_fewer_than_max(self) -> None:
        conv = self._build_conversation(5)
        window = conv.get_context_window(max_messages=50)
        assert len(window) == 5

    def test_returns_last_n_when_exceeding_max(self) -> None:
        conv = self._build_conversation(10)
        window = conv.get_context_window(max_messages=3)
        assert len(window) == 3
        assert window[0].content == "Message 7"
        assert window[1].content == "Message 8"
        assert window[2].content == "Message 9"

    def test_returns_all_when_equal_to_max(self) -> None:
        conv = self._build_conversation(5)
        window = conv.get_context_window(max_messages=5)
        assert len(window) == 5

    def test_empty_conversation_returns_empty(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        window = conv.get_context_window()
        assert window == []

    def test_default_max_messages_is_50(self) -> None:
        conv = self._build_conversation(60)
        window = conv.get_context_window()
        assert len(window) == 50
        assert window[0].content == "Message 10"

    def test_invalid_max_messages_raises(self) -> None:
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        with pytest.raises(ValueError, match="must be positive"):
            conv.get_context_window(max_messages=0)
        with pytest.raises(ValueError, match="must be positive"):
            conv.get_context_window(max_messages=-1)

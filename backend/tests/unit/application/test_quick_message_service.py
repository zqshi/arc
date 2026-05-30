"""Unit tests for application/todo/quick_message_service.py."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.todo.quick_message_service import run_ai_response


@pytest.fixture
def conversation_id():
    return uuid.uuid4()


@pytest.fixture
def todo_id():
    return str(uuid.uuid4())


@pytest.fixture
def project_id():
    return str(uuid.uuid4())


class TestRunAiResponse:
    """Tests for run_ai_response background coroutine."""

    @pytest.mark.asyncio
    async def test_returns_early_when_conversation_not_found(
        self, conversation_id, todo_id, project_id
    ):
        mock_db = AsyncMock()
        mock_conv_repo = AsyncMock()
        mock_conv_repo.get_by_id.return_value = None

        with (
            patch(
                "arc.application.todo.quick_message_service.async_session_factory"
            ) as mock_factory,
            patch(
                "arc.application.todo.quick_message_service.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "arc.application.todo.quick_message_service.ConversationExecutionService"
            ) as mock_svc_cls,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            await run_ai_response(
                conversation_id=conversation_id,
                todo_id=todo_id,
                project_id=project_id,
            )

            mock_conv_repo.get_by_id.assert_called_once_with(conversation_id)
            mock_svc_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_streams_chunks_and_emits_task_events(
        self, conversation_id, todo_id, project_id
    ):
        mock_db = AsyncMock()
        mock_conv = MagicMock()
        mock_conv_repo = AsyncMock()
        mock_conv_repo.get_by_id.return_value = mock_conv

        chunks = [
            {"message_id": "msg-1", "content": "Hello "},
            {"content": "world"},
        ]

        mock_svc = AsyncMock()

        async def fake_stream(conv):
            for c in chunks:
                yield c

        mock_svc.generate_response_stream = fake_stream

        with (
            patch(
                "arc.application.todo.quick_message_service.async_session_factory"
            ) as mock_factory,
            patch(
                "arc.application.todo.quick_message_service.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "arc.application.todo.quick_message_service.ConversationExecutionService",
                return_value=mock_svc,
            ),
            patch(
                "arc.application.todo.quick_message_service.project_task_stream"
            ) as mock_stream,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_stream.emit = AsyncMock()

            await run_ai_response(
                conversation_id=conversation_id,
                todo_id=todo_id,
                project_id=project_id,
            )

            # Should emit task_status "running" on first chunk
            calls = mock_stream.emit.call_args_list
            events = [c[0][1] for c in calls]
            assert any(e["event"] == "task_status" and e["status"] == "running" for e in events)
            # Should emit task_chunk for each content chunk
            assert any(e["event"] == "task_chunk" and e["content"] == "Hello " for e in events)
            # Should emit idle at the end (finally block)
            assert events[-1]["event"] == "task_status"
            assert events[-1]["status"] == "idle"
            mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_emits_error_event_on_exception(
        self, conversation_id, todo_id, project_id
    ):
        mock_db = AsyncMock()
        mock_conv = MagicMock()
        mock_conv_repo = AsyncMock()
        mock_conv_repo.get_by_id.return_value = mock_conv

        mock_svc = AsyncMock()

        async def failing_stream(conv):
            raise RuntimeError("LLM exploded")
            yield  # pragma: no cover — makes this an async generator

        mock_svc.generate_response_stream = failing_stream

        with (
            patch(
                "arc.application.todo.quick_message_service.async_session_factory"
            ) as mock_factory,
            patch(
                "arc.application.todo.quick_message_service.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "arc.application.todo.quick_message_service.ConversationExecutionService",
                return_value=mock_svc,
            ),
            patch(
                "arc.application.todo.quick_message_service.project_task_stream"
            ) as mock_stream,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_stream.emit = AsyncMock()

            await run_ai_response(
                conversation_id=conversation_id,
                todo_id=todo_id,
                project_id=project_id,
            )

            calls = mock_stream.emit.call_args_list
            events = [c[0][1] for c in calls]
            # Should emit error status
            assert any(e["event"] == "task_status" and e["status"] == "error" for e in events)
            # Should still emit idle in finally
            assert events[-1]["status"] == "idle"
            mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_no_task_events_without_project_id(self, conversation_id, todo_id):
        mock_db = AsyncMock()
        mock_conv = MagicMock()
        mock_conv_repo = AsyncMock()
        mock_conv_repo.get_by_id.return_value = mock_conv

        mock_svc = AsyncMock()

        async def fake_stream(conv):
            yield {"message_id": "msg-1", "content": "response"}

        mock_svc.generate_response_stream = fake_stream

        with (
            patch(
                "arc.application.todo.quick_message_service.async_session_factory"
            ) as mock_factory,
            patch(
                "arc.application.todo.quick_message_service.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "arc.application.todo.quick_message_service.ConversationExecutionService",
                return_value=mock_svc,
            ),
            patch(
                "arc.application.todo.quick_message_service.project_task_stream"
            ) as mock_stream,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_stream.emit = AsyncMock()

            await run_ai_response(
                conversation_id=conversation_id,
                todo_id=todo_id,
                project_id=None,  # No project
            )

            mock_stream.emit.assert_not_called()
            mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_artifacts_extracted_event_emits_task_done(
        self, conversation_id, todo_id, project_id
    ):
        mock_db = AsyncMock()
        mock_conv = MagicMock()
        mock_conv_repo = AsyncMock()
        mock_conv_repo.get_by_id.return_value = mock_conv

        mock_svc = AsyncMock()

        async def fake_stream(conv):
            yield {"event": "artifacts_extracted", "artifact_names": ["doc.md"]}

        mock_svc.generate_response_stream = fake_stream

        with (
            patch(
                "arc.application.todo.quick_message_service.async_session_factory"
            ) as mock_factory,
            patch(
                "arc.application.todo.quick_message_service.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "arc.application.todo.quick_message_service.ConversationExecutionService",
                return_value=mock_svc,
            ),
            patch(
                "arc.application.todo.quick_message_service.project_task_stream"
            ) as mock_stream,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_stream.emit = AsyncMock()

            await run_ai_response(
                conversation_id=conversation_id,
                todo_id=todo_id,
                project_id=project_id,
            )

            calls = mock_stream.emit.call_args_list
            events = [c[0][1] for c in calls]
            assert any(
                e["event"] == "task_done" and e["artifacts"] == ["doc.md"] for e in events
            )

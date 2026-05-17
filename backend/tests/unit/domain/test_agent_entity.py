from __future__ import annotations

import uuid

import pytest

from arc.domain.agent.entity import AgentSession
from arc.domain.agent.value_objects import AgentType, SessionStatus


class TestAgentSessionCreation:
    def test_create_with_defaults(self) -> None:
        session = AgentSession(
            todo_id=uuid.uuid4(),
            phase_id=uuid.uuid4(),
            agent_type=AgentType.OPENHANDS,
        )
        assert isinstance(session.id, uuid.UUID)
        assert session.status == SessionStatus.PENDING
        assert session.external_session_id == ""
        assert session.task_context == {}
        assert session.result_summary == {}
        assert session.error_reason == ""
        assert session.started_at is None
        assert session.completed_at is None
        assert not session.is_terminal


class TestAgentSessionTransitions:
    def _make_session(self) -> AgentSession:
        return AgentSession(
            todo_id=uuid.uuid4(),
            phase_id=uuid.uuid4(),
            agent_type=AgentType.OPENHANDS,
        )

    def test_start(self) -> None:
        s = self._make_session()
        s.start("ext-123")
        assert s.status == SessionStatus.RUNNING
        assert s.external_session_id == "ext-123"
        assert s.started_at is not None

    def test_complete(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.complete()
        assert s.status == SessionStatus.COMPLETED
        assert s.completed_at is not None
        assert s.is_terminal

    def test_mark_error(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.mark_error("timeout")
        assert s.status == SessionStatus.ERROR
        assert s.error_reason == "timeout"
        assert s.is_terminal

    def test_cancel_from_pending(self) -> None:
        s = self._make_session()
        s.cancel()
        assert s.status == SessionStatus.CANCELLED
        assert s.is_terminal

    def test_cancel_from_running(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.cancel()
        assert s.status == SessionStatus.CANCELLED

    def test_pause_and_resume(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.pause()
        assert s.status == SessionStatus.PAUSED
        s.resume()
        assert s.status == SessionStatus.RUNNING

    def test_retry_from_error(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.mark_error("oops")
        s.retry()
        assert s.status == SessionStatus.PENDING
        assert s.error_reason == ""
        assert s.external_session_id == ""

    def test_invalid_transition_raises(self) -> None:
        s = self._make_session()
        with pytest.raises(Exception):
            s.complete()  # cannot complete from pending

    def test_cannot_start_completed(self) -> None:
        s = self._make_session()
        s.start("ext-1")
        s.complete()
        with pytest.raises(Exception):
            s.start("ext-2")


class TestAgentTypeLabels:
    def test_all_types_have_labels(self) -> None:
        from arc.domain.agent.value_objects import AGENT_LABELS
        for agent_type in AgentType:
            assert agent_type in AGENT_LABELS


class TestSessionStatusTransitions:
    def test_valid_transitions_cover_all_statuses(self) -> None:
        from arc.domain.agent.value_objects import VALID_SESSION_TRANSITIONS
        for status in SessionStatus:
            assert status in VALID_SESSION_TRANSITIONS

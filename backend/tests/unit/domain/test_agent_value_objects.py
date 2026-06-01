"""Tests for domain/agent value objects."""

from arc.domain.agent.value_objects import (
    AGENT_LABELS,
    VALID_SESSION_TRANSITIONS,
    AgentType,
    SessionStatus,
)


class TestAgentType:
    def test_enum_values(self):
        assert AgentType.OPENHANDS == "openhands"
        assert AgentType.CODEX == "codex"
        assert AgentType.CLAUDE_CODE == "claude_code"
        assert AgentType.CURSOR == "cursor"

    def test_enum_completeness(self):
        expected = {"openhands", "codex", "claude_code", "cursor"}
        assert {m.value for m in AgentType} == expected

    def test_equality_same_value(self):
        assert AgentType.OPENHANDS == AgentType("openhands")

    def test_equality_string_coercion(self):
        assert AgentType.CODEX == "codex"

    def test_invalid_value_raises(self):
        try:
            AgentType("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_all_types_have_labels(self):
        for agent_type in AgentType:
            assert agent_type in AGENT_LABELS


class TestSessionStatus:
    def test_enum_values(self):
        assert SessionStatus.PENDING == "pending"
        assert SessionStatus.RUNNING == "running"
        assert SessionStatus.PAUSED == "paused"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.ERROR == "error"
        assert SessionStatus.CANCELLED == "cancelled"

    def test_enum_completeness(self):
        expected = {"pending", "running", "paused", "completed", "error", "cancelled"}
        assert {s.value for s in SessionStatus} == expected

    def test_equality_same_value(self):
        assert SessionStatus.RUNNING == SessionStatus("running")

    def test_invalid_value_raises(self):
        try:
            SessionStatus("invalid")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestValidSessionTransitions:
    def test_all_statuses_covered(self):
        assert set(VALID_SESSION_TRANSITIONS.keys()) == set(SessionStatus)

    def test_pending_transitions(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.PENDING] == {
            SessionStatus.RUNNING,
            SessionStatus.CANCELLED,
        }

    def test_running_transitions(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.RUNNING] == {
            SessionStatus.PAUSED,
            SessionStatus.COMPLETED,
            SessionStatus.ERROR,
            SessionStatus.CANCELLED,
        }

    def test_paused_transitions(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.PAUSED] == {
            SessionStatus.RUNNING,
            SessionStatus.CANCELLED,
        }

    def test_completed_is_terminal(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.COMPLETED] == set()

    def test_cancelled_is_terminal(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.CANCELLED] == set()

    def test_error_can_retry(self):
        assert VALID_SESSION_TRANSITIONS[SessionStatus.ERROR] == {
            SessionStatus.PENDING,
        }


class TestAgentLabels:
    def test_all_agent_types_have_labels(self):
        for agent_type in AgentType:
            assert agent_type in AGENT_LABELS
            assert isinstance(AGENT_LABELS[agent_type], str)
            assert len(AGENT_LABELS[agent_type]) > 0

    def test_label_values(self):
        assert AGENT_LABELS[AgentType.OPENHANDS] == "OpenHands"
        assert AGENT_LABELS[AgentType.CODEX] == "Codex"
        assert AGENT_LABELS[AgentType.CLAUDE_CODE] == "Claude Code"
        assert AGENT_LABELS[AgentType.CURSOR] == "Cursor"

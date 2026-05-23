"""Unit tests for AgentLoop._is_structurally_incomplete."""

from arc.application.execution.agent_loop import AgentLoop


class TestIsTruncated:
    def test_complete_json(self):
        assert AgentLoop._is_structurally_incomplete('{"a": 1}') is False

    def test_unclosed_brace(self):
        assert AgentLoop._is_structurally_incomplete('{"a": {"b": 1}') is True

    def test_unclosed_bracket(self):
        assert AgentLoop._is_structurally_incomplete('[{"a": 1},') is True

    def test_unclosed_code_fence(self):
        assert AgentLoop._is_structurally_incomplete('```json\n{"a": 1}') is True

    def test_closed_code_fence(self):
        assert AgentLoop._is_structurally_incomplete('```json\n{"a": 1}\n```') is False

    def test_empty(self):
        assert AgentLoop._is_structurally_incomplete('') is False

    def test_plain_text(self):
        assert AgentLoop._is_structurally_incomplete('Hello, this is complete.') is False

    def test_nested_json_truncated(self):
        content = '{"entities": [{"name": "User", "fields": [{"name": "id"'
        assert AgentLoop._is_structurally_incomplete(content) is True

"""Unit tests for AgentLoop._is_heuristic_truncated."""

from arc.application.execution.agent_loop import AgentLoop


class TestIsTruncated:
    def test_complete_json(self):
        assert AgentLoop._is_heuristic_truncated('{"a": 1}') is False

    def test_unclosed_brace(self):
        assert AgentLoop._is_heuristic_truncated('{"a": {"b": 1}') is True

    def test_unclosed_bracket(self):
        assert AgentLoop._is_heuristic_truncated('[{"a": 1},') is True

    def test_unclosed_code_fence(self):
        assert AgentLoop._is_heuristic_truncated('```json\n{"a": 1}') is True

    def test_closed_code_fence(self):
        assert AgentLoop._is_heuristic_truncated('```json\n{"a": 1}\n```') is False

    def test_empty(self):
        assert AgentLoop._is_heuristic_truncated('') is False

    def test_plain_text(self):
        assert AgentLoop._is_heuristic_truncated('Hello, this is complete.') is False

    def test_nested_json_truncated(self):
        content = '{"entities": [{"name": "User", "fields": [{"name": "id"'
        assert AgentLoop._is_heuristic_truncated(content) is True

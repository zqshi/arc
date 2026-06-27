"""Unit tests for execution_engine — pure function tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from arc.application.execution.execution_engine import _map_tool_event, _needs_user_input


class TestNeedsUserInput:
    def test_explicit_marker(self) -> None:
        assert _needs_user_input("[NEEDS_INPUT] 请确认方案") is True

    def test_question_mark_zh(self) -> None:
        assert _needs_user_input("你觉得这样如何？") is True

    def test_question_mark_en(self) -> None:
        assert _needs_user_input("What do you think?") is True

    def test_confirm_phrase(self) -> None:
        assert _needs_user_input("请确认上述方案。") is True

    def test_choice_phrase(self) -> None:
        assert _needs_user_input("方案A和方案B各有利弊，你选择哪个") is True

    def test_no_question(self) -> None:
        assert _needs_user_input("我已经完成了需求分析。以下是结果。") is False

    def test_empty_string(self) -> None:
        assert _needs_user_input("") is False

    def test_question_in_middle_not_end(self) -> None:
        content = "你觉得好吗？\n\n好的，我来继续推进。以下是最终方案。"
        assert _needs_user_input(content) is False

    def test_preference_phrase(self) -> None:
        assert _needs_user_input("这两种方案你倾向哪个") is True


class TestMapToolEvent:
    def test_text_delta(self) -> None:
        event = MagicMock()
        event.type = "text_delta"
        event.content = "Hello"
        event.metadata = {"message_id": "msg-1"}
        results = _map_tool_event(event)
        assert len(results) == 1
        assert results[0]["content"] == "Hello"
        assert results[0]["message_id"] == "msg-1"

    def test_tool_call(self) -> None:
        event = MagicMock()
        event.type = "tool_call"
        event.content = "read_file"
        event.metadata = {"input": {"path": "main.py"}, "round": 1, "parallel": True}
        results = _map_tool_event(event)
        assert len(results) == 1
        assert results[0]["event"] == "tool_call"
        assert results[0]["tool_name"] == "read_file"
        assert results[0]["parallel"] is True

    def test_tool_result(self) -> None:
        event = MagicMock()
        event.type = "tool_result"
        event.content = "file content..."
        event.metadata = {"tool_name": "read_file", "is_error": False, "parallel": False}
        results = _map_tool_event(event)
        assert len(results) == 1
        assert results[0]["event"] == "tool_result"
        assert results[0]["is_error"] is False

    def test_orchestration_start(self) -> None:
        event = MagicMock()
        event.type = "orchestration_start"
        event.metadata = {"plan_id": "abc", "subtask_count": 3}
        results = _map_tool_event(event)
        assert results[0]["event"] == "orchestration_start"
        assert results[0]["subtask_count"] == 3

    def test_complete_emits_metrics(self) -> None:
        event = MagicMock()
        event.type = "complete"
        event.content = ""
        event.metadata = {"tool_rounds": 5, "total_tokens": 1000, "elapsed_ms": 3000}
        results = _map_tool_event(event)
        assert results[0]["event"] == "complete_metrics"
        assert results[0]["metrics"]["tool_rounds"] == 5

    def test_error_returns_tool_error_event(self) -> None:
        event = MagicMock()
        event.type = "error"
        event.content = "something broke"
        event.metadata = {"message_id": "msg-1"}
        results = _map_tool_event(event)
        assert len(results) == 1
        assert results[0]["event"] == "tool_error"
        assert results[0]["detail"] == "something broke"
        assert results[0]["message_id"] == "msg-1"

    def test_approval_required(self) -> None:
        event = MagicMock()
        event.type = "approval_required"
        event.metadata = {"request_id": "r1", "tool_name": "write_file"}
        results = _map_tool_event(event)
        assert results[0]["event"] == "approval_required"

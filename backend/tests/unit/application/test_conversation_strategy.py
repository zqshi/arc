from __future__ import annotations

from arc.application.execution.execution_engine import _needs_user_input


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
        assert _needs_user_input(
            "方案A和方案B各有利弊，你选择哪个"
        ) is True

    def test_no_question(self) -> None:
        assert _needs_user_input(
            "我已经完成了需求分析。以下是结果。"
        ) is False

    def test_empty_string(self) -> None:
        assert _needs_user_input("") is False

    def test_question_in_middle_not_end(self) -> None:
        content = "你觉得好吗？\n\n好的，我来继续推进。以下是最终方案。"
        assert _needs_user_input(content) is False

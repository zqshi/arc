from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

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


class TestBuildContextAwareGreeting:
    """v5.1.0: 上下文感知 greeting 逻辑。"""

    @pytest.fixture
    def service(self):
        from arc.application.execution.conversation_strategy import ConversationExecutionService
        mock_db = AsyncMock()
        with patch("arc.application.execution.conversation_strategy.TodoRepository"), \
             patch("arc.application.execution.conversation_strategy.ConversationRepository"), \
             patch("arc.application.execution.conversation_strategy.ArtifactRepository"), \
             patch("arc.application.execution.conversation_strategy.DeliverableTrackerRepository"):
            svc = ConversationExecutionService(mock_db)
            yield svc

    @pytest.mark.asyncio
    async def test_greeting_contains_title(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(title="实现登录功能")
        with patch.object(service, "_get_project_constraint", return_value="free"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=""):
            greeting = await service._build_context_aware_greeting(todo)
        assert "实现登录功能" in greeting

    @pytest.mark.asyncio
    async def test_greeting_shows_constraint_strict(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(title="测试")
        with patch.object(service, "_get_project_constraint", return_value="strict"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=""):
            greeting = await service._build_context_aware_greeting(todo)
        assert "标准研发流程" in greeting

    @pytest.mark.asyncio
    async def test_greeting_shows_analysis_insight(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(title="测试")
        insight = "版本分析中对此需求的定位：**[P0]** 核心功能"
        with patch.object(service, "_get_project_constraint", return_value="free"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=insight):
            greeting = await service._build_context_aware_greeting(todo)
        assert "P0" in greeting
        assert "核心功能" in greeting

    @pytest.mark.asyncio
    async def test_greeting_source_awareness(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(title="AI推荐需求", source_session_id=uuid.uuid4())
        with patch.object(service, "_get_project_constraint", return_value="free"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=""):
            greeting = await service._build_context_aware_greeting(todo)
        assert "版本分析建议" in greeting

    @pytest.mark.asyncio
    async def test_greeting_rich_description_skips_question(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(
            title="重构登录",
            description="[P0] 来源：AI 迭代分析建议。需要将现有 session 改为 JWT。"
        )
        with patch.object(service, "_get_project_constraint", return_value="free"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=""):
            greeting = await service._build_context_aware_greeting(todo)
        assert "直接开始推进" in greeting
        assert "解决什么问题" not in greeting

    @pytest.mark.asyncio
    async def test_greeting_no_description_asks(self, service):
        from arc.domain.todo.entity import Todo
        todo = Todo(title="新功能")
        with patch.object(service, "_get_project_constraint", return_value="free"), \
             patch.object(service, "_get_analysis_insight_for_greeting", return_value=""):
            greeting = await service._build_context_aware_greeting(todo)
        assert "解决什么问题" in greeting

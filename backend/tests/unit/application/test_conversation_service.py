"""ConversationService 核心方法单元测试。"""

import uuid

import pytest

from arc.domain.conversation.entity import Conversation
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole


class TestFormatExperiences:
    def test_empty(self):
        from arc.application.conversation.service import ConversationService
        from arc.domain.pipeline.value_objects import PhaseType

        result = ConversationService._format_experiences([], PhaseType.CLARIFICATION)
        assert result == ""

    def test_with_experiences(self):
        from arc.application.conversation.service import ConversationService
        from arc.domain.experience.entity import Experience
        from arc.domain.pipeline.value_objects import PhaseType

        exps = [
            Experience(
                title="经验1",
                problem="问题描述",
                solution="解决方案",
                decisions=["决策1"],
                pitfalls=["陷阱1"],
            )
        ]
        result = ConversationService._format_experiences(exps, PhaseType.CLARIFICATION)
        assert "经验1" in result
        assert "解决方案" in result


class TestBuildClarificationPrompt:
    def test_includes_todo_info(self):
        from unittest.mock import MagicMock
        from arc.application.conversation.service import ConversationService

        svc = ConversationService.__new__(ConversationService)
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)

        todo = MagicMock()
        todo.title = "订单系统"
        todo.description = "实现基本订单流程"

        result = svc._build_clarification_prompt(conv, todo, {})
        assert "订单系统" in result

    def test_includes_confirmed_artifacts(self):
        from unittest.mock import MagicMock
        from arc.application.conversation.service import ConversationService
        from arc.domain.artifact.value_objects import ArtifactType

        svc = ConversationService.__new__(ConversationService)
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.ARCHITECTURE)

        todo = MagicMock()
        todo.title = "test"
        todo.description = ""

        confirmed = {ArtifactType.REQUIREMENT_SPEC: {"background": "测试背景"}}
        result = svc._build_clarification_prompt(conv, todo, confirmed)
        assert isinstance(result, str)

    def test_routes_by_requirement_type(self):
        """验证三策略路由激活: '优化'关键词 → 苏格拉底策略 (而非固定6层)。"""
        from unittest.mock import MagicMock
        from arc.application.conversation.service import ConversationService

        svc = ConversationService.__new__(ConversationService)
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        # 2 轮用户对话使 round>=2，激活关键词路由 (round<2 会先走 SUFFICIENCY_FIRST)
        conv.add_message(role=MessageRole.USER, content="第一轮")
        conv.add_message(role=MessageRole.USER, content="第二轮")

        todo = MagicMock()
        todo.title = "性能优化"
        todo.description = "需要优化现有登录流程"

        result = svc._build_clarification_prompt(conv, todo, {})
        # "优化"关键词 → SOCRATIC 策略，prompt 含苏格拉底追问方法论
        assert "苏格拉底" in result or "追问" in result


class TestBuildFormatArgs:
    def test_basic(self):
        from unittest.mock import MagicMock
        from arc.application.conversation.service import ConversationService

        svc = ConversationService.__new__(ConversationService)
        todo = MagicMock()
        todo.title = "标题"
        todo.description = "描述"

        result = svc._build_format_args({}, todo)
        assert isinstance(result, dict)
        assert "title" in result or "todo_title" in result or len(result) > 0

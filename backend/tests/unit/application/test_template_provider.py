"""Tests for TemplateProvider (v5.7.0 T8).

ARCHITECTURE 阶段匹配历史模板注入上下文, 供 Agent 参考可复用骨架。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


def _make_template(title="电商模板", score=0.85) -> DomainTemplate:
    t = DomainTemplate(
        title=title,
        description="电商订单骨架",
        category=TemplateCategory.ECOMMERCE,
        source_user_id=uuid.uuid4(),
        status=TemplateStatus.PUBLISHED,
        usage_count=5,
        success_count=4,
        entity_patterns=["master-detail (主从关系)"],
        state_machine_patterns=["chain (链式状态机, 3 步)"],
        permission_patterns=["owner-based (按拥有者隔离)"],
    )
    return t


class TestTemplateProvider:
    @pytest.mark.asyncio
    async def test_architecture_phase_injects_template(self):
        """ARCHITECTURE 阶段 + 有匹配模板 → 注入 ContextSegment。"""
        from arc.application.context.providers.template import TemplateProvider

        todo = MagicMock()
        todo.title = "做一个电商订单系统"
        todo.description = "含订单和支付"
        todo.project_id = uuid.uuid4()
        todo.current_phase = PhaseType.ARCHITECTURE

        request = MagicMock()
        request.todo = todo

        provider = TemplateProvider.__new__(TemplateProvider)
        provider._db = MagicMock()

        with patch(
            "arc.application.template.matching_service.TemplateMatchingService"
        ) as MockMatching:
            mock_matching = MagicMock()
            mock_matching.search_matching = AsyncMock(return_value=[
                (_make_template("电商订单模板"), 0.88),
            ])
            MockMatching.return_value = mock_matching

            segments = await provider.provide(request)

            assert len(segments) == 1
            assert "电商订单模板" in segments[0].content
            assert "master-detail" in segments[0].content or "主从" in segments[0].content

    @pytest.mark.asyncio
    async def test_non_architecture_phase_skipped(self):
        """非 ARCHITECTURE 阶段不注入模板 (模板是架构决策参考)。"""
        from arc.application.context.providers.template import TemplateProvider

        todo = MagicMock()
        todo.title = "做电商"
        todo.current_phase = PhaseType.DEVELOPMENT
        request = MagicMock()
        request.todo = todo

        provider = TemplateProvider.__new__(TemplateProvider)
        provider._db = MagicMock()

        with patch(
            "arc.application.template.matching_service.TemplateMatchingService"
        ) as MockMatching:
            mock_matching = MagicMock()
            mock_matching.search_matching = AsyncMock()
            MockMatching.return_value = mock_matching

            segments = await provider.provide(request)
            assert segments == []
            mock_matching.search_matching.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_matching_templates_returns_empty(self):
        """无匹配模板 → 空列表 (不注入)。"""
        from arc.application.context.providers.template import TemplateProvider

        todo = MagicMock()
        todo.title = "做一个独特的系统"
        todo.description = ""
        todo.current_phase = PhaseType.ARCHITECTURE
        request = MagicMock()
        request.todo = todo

        provider = TemplateProvider.__new__(TemplateProvider)
        provider._db = MagicMock()

        with patch(
            "arc.application.template.matching_service.TemplateMatchingService"
        ) as MockMatching:
            mock_matching = MagicMock()
            mock_matching.search_matching = AsyncMock(return_value=[])
            MockMatching.return_value = mock_matching

            segments = await provider.provide(request)
            assert segments == []

    @pytest.mark.asyncio
    async def test_provider_failure_returns_empty(self):
        """Provider 异常 → 空列表 (不阻断, 仅 debug 日志)。"""
        from arc.application.context.providers.template import TemplateProvider

        todo = MagicMock()
        todo.title = "q"
        todo.current_phase = PhaseType.ARCHITECTURE
        request = MagicMock()
        request.todo = todo

        provider = TemplateProvider.__new__(TemplateProvider)
        provider._db = MagicMock()

        with patch(
            "arc.application.template.matching_service.TemplateMatchingService"
        ) as MockMatching:
            mock_matching = MagicMock()
            mock_matching.search_matching = AsyncMock(side_effect=Exception("db down"))
            MockMatching.return_value = mock_matching

            segments = await provider.provide(request)
            assert segments == []

    @pytest.mark.asyncio
    async def test_no_todo_returns_empty(self):
        from arc.application.context.providers.template import TemplateProvider

        request = MagicMock()
        request.todo = None

        provider = TemplateProvider.__new__(TemplateProvider)
        provider._db = MagicMock()

        segments = await provider.provide(request)
        assert segments == []

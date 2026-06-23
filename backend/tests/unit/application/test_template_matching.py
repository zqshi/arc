"""Tests for TemplateMatchingService (v5.7.0 T5).

语义匹配: 需求描述 → embedding → 向量搜索 → 推荐 (含质量门控)。
mock embedding 生成 + repository, 验证编排逻辑。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


def _make_template(
    *, title: str = "电商模板", category=TemplateCategory.ECOMMERCE, usage=5
) -> DomainTemplate:
    t = DomainTemplate(
        title=title,
        description="测试模板",
        category=category,
        source_user_id=uuid.uuid4(),
        status=TemplateStatus.PUBLISHED,
        usage_count=usage,
    )
    return t


class TestSearchMatching:
    @pytest.mark.asyncio
    async def test_returns_matched_templates_with_scores(self):
        """需求 → embedding → 向量搜索 → 返回 (template, score) 列表。"""
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )

        t1 = _make_template(title="电商订单模板")
        t2 = _make_template(title="商城模板")

        repo = MagicMock()
        repo.search_by_embedding = AsyncMock(return_value=[
            (t1, 0.92),
            (t2, 0.85),
        ])

        svc = TemplateMatchingService.__new__(TemplateMatchingService)
        svc._repo = repo

        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            results = await svc.search_matching("做一个电商订单系统")

            assert len(results) == 2
            template, score = results[0]
            assert template.title == "电商订单模板"
            assert score == 0.92

    @pytest.mark.asyncio
    async def test_filters_below_similarity_threshold(self):
        """相似度低于阈值的结果被丢弃 (质量门控)。"""
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )

        t1 = _make_template(title="高相关")
        t2 = _make_template(title="低相关")

        repo = MagicMock()
        repo.search_by_embedding = AsyncMock(return_value=[
            (t1, 0.85),
            (t2, 0.30),  # 低于阈值
        ])

        svc = TemplateMatchingService.__new__(TemplateMatchingService)
        svc._repo = repo

        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            results = await svc.search_matching("query")

            assert len(results) == 1
            assert results[0][0].title == "高相关"

    @pytest.mark.asyncio
    async def test_embedding_failure_returns_empty(self):
        """embedding 生成失败 → 空列表 (不抛错)。"""
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )

        repo = MagicMock()
        svc = TemplateMatchingService.__new__(TemplateMatchingService)
        svc._repo = repo

        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(side_effect=Exception("LLM down"))
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            results = await svc.search_matching("query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_overretrieves_then_filters(self):
        """过宽检索 (2x) 后阈值过滤 (同 Experience 质量门控)。"""
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )

        repo = MagicMock()
        # 验证检索时传 limit * 2
        repo.search_by_embedding = AsyncMock(return_value=[])

        svc = TemplateMatchingService.__new__(TemplateMatchingService)
        svc._repo = repo

        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            await svc.search_matching("query", limit=5)

            call_args = repo.search_by_embedding.call_args
            assert call_args.kwargs["limit"] == 10  # 2x 过宽

    @pytest.mark.asyncio
    async def test_results_ordered_by_similarity(self):
        """结果按相似度降序 (repository 已排序, service 不打乱)。"""
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )

        t1 = _make_template(title="最相关")
        t2 = _make_template(title="次相关")
        t3 = _make_template(title="第三")

        repo = MagicMock()
        repo.search_by_embedding = AsyncMock(return_value=[
            (t1, 0.95), (t2, 0.80), (t3, 0.65),
        ])

        svc = TemplateMatchingService.__new__(TemplateMatchingService)
        svc._repo = repo

        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            results = await svc.search_matching("query")
            scores = [s for _, s in results]
            assert scores == [0.95, 0.80, 0.65]

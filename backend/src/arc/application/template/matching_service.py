"""TemplateMatchingService — 语义匹配 + 推荐 (v5.7.0 T5)。

流程: 需求描述 → LLM embedding → 向量搜索 → 质量门控 → 推荐列表
质量门控 (同 Experience):
1. 过宽检索 (2x limit)
2. 低于 SIMILARITY_THRESHOLD 丢弃
3. (单一模板无 category 多样性问题, 跳过该步)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from arc.domain.template.entity import DomainTemplate

if TYPE_CHECKING:
    from arc.infrastructure.repositories.template import TemplateRepository

logger = logging.getLogger(__name__)

# 相似度阈值 (同 Experience), 低于此值视为不相关
SIMILARITY_THRESHOLD = 0.5


class TemplateMatchingService:
    """新项目需求 → 匹配历史模板并推荐。"""

    def __init__(self, repo: TemplateRepository) -> None:
        self._repo = repo

    async def search_matching(
        self, query: str, *, limit: int = 5
    ) -> list[tuple[DomainTemplate, float]]:
        """需求描述 → 推荐 (template, similarity) 列表。

        Args:
            query: 需求描述文本
            limit: 返回数量上限

        Returns:
            (template, similarity) 元组, 按相似度降序, 已过滤低质量结果
        """
        from arc.application.ai.resilience import create_resilient_adapter

        # 1. 生成 query embedding
        try:
            adapter = create_resilient_adapter()
        except Exception as exc:
            logger.warning("matching: adapter creation failed: %s", exc)
            return []
        try:
            embedding = await adapter.embed(query)
        except Exception as exc:
            logger.warning("matching: embedding generation failed: %s", exc)
            return []
        finally:
            await adapter.close()

        # 2. 过宽检索 (2x, 留过滤空间)
        try:
            scored = await self._repo.search_by_embedding(
                embedding, limit=limit * 2
            )
        except Exception as exc:
            logger.warning("matching: vector search failed: %s", exc)
            return []

        # 3. 质量门控: 阈值过滤
        filtered = [
            (t, score) for t, score in scored
            if score >= SIMILARITY_THRESHOLD
        ]

        # 4. 截取到 limit
        return filtered[:limit]

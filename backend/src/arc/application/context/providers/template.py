"""模板推荐上下文 Provider — ARCHITECTURE 阶段注入匹配的历史模板 (v5.7.0 T8)。

模板是"可执行骨架" (强绑定), 比经验 (弱绑定) 更具体。
ARCHITECTURE 阶段 Agent 可参考匹配模板的实体模式/状态机/权限模式做架构决策,
选中后可一键 apply 到 Supabase (TemplateApplyService)。
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment
from arc.domain.pipeline.value_objects import PhaseType

logger = logging.getLogger(__name__)


class TemplateProvider:
    """ARCHITECTURE 阶段注入语义匹配的历史领域模型模板。"""

    source = "template"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo:
            return []

        # 仅 ARCHITECTURE 阶段注入 (模板是架构决策参考)
        if getattr(request.todo, "current_phase", None) != PhaseType.ARCHITECTURE:
            return []

        try:
            content = await self._build(request.todo)
            if not content:
                return []
            return [ContextSegment(
                source=self.source,
                priority=1,  # 参考信息, 可压缩
                content=content,
            )]
        except Exception:
            logger.debug("TemplateProvider failed", exc_info=True)
            return []

    async def _build(self, todo) -> str:
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )
        from arc.infrastructure.repositories.template import TemplateRepository

        # 用 todo 标题+描述作 query 匹配
        query = f"{todo.title} {getattr(todo, 'description', '') or ''}".strip()
        if not query:
            return ""

        repo = TemplateRepository(self._db)
        svc = TemplateMatchingService(repo)
        results = await svc.search_matching(query, limit=3)
        if not results:
            return ""

        lines = [f"## 历史领域模型模板推荐 ({len(results)} 个匹配)"]
        for template, score in results:
            lines.append(f"### {template.title} (相似度 {score:.2f})")
            lines.append(f"- 分类: {template.category.value}")
            lines.append(f"- 描述: {template.description}")
            if template.entity_patterns:
                lines.append(f"- 实体模式: {', '.join(template.entity_patterns)}")
            if template.state_machine_patterns:
                lines.append(
                    f"- 状态机: {', '.join(template.state_machine_patterns)}"
                )
            if template.permission_patterns:
                lines.append(
                    f"- 权限模式: {', '.join(template.permission_patterns)}"
                )
            lines.append(
                f"- 使用统计: {template.usage_count} 次, "
                f"成功率 {template.success_rate:.0%}"
            )
        lines.append("\n(可参考这些模式设计领域模型; 选中模板可一键 apply)")
        return "\n".join(lines)

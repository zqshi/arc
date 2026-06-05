"""领域模型 Provider — 注入聚合、子域、上下文关系等结构化模型信息。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class DomainModelProvider:
    """注入项目领域模型（聚合、子域、上下文、关系）。"""

    source = "domain_model"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo or not request.todo.project_id:
            return []

        try:
            from arc.application.context.prompts import build_ddd_tdd_section
            from arc.infrastructure.repositories.project import ProjectRepository

            project = await ProjectRepository(self._db).get_by_id(
                request.todo.project_id
            )
            if not project or not project.domain_model:
                return []

            content = build_ddd_tdd_section(project.domain_model)
            if not content:
                return []

            return [ContextSegment(
                source=self.source,
                priority=1,
                content=content,
                metadata={
                    "model_version": project.domain_model.get("version", 0),
                    "source": project.domain_model.get("source", "unknown"),
                },
            )]
        except Exception:
            logger.debug("DomainModelProvider failed", exc_info=True)
            return []

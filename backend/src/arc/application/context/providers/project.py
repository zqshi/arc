"""项目基础信息 Provider。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class ProjectInfoProvider:
    """注入项目名称、描述、技术栈、版本目标等基础信息。"""

    source = "project"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo or not request.todo.project_id:
            return []

        try:
            from arc.application.context.provider import ProjectContextProvider

            ctx_provider = ProjectContextProvider(self._db)
            project_ctx = await ctx_provider.get_context(request.conversation.todo_id)
            content = project_ctx.to_prompt_section()
            if not content:
                return []

            return [ContextSegment(
                source=self.source,
                priority=1,
                content=content,
            )]
        except Exception:
            logger.debug("ProjectInfoProvider failed", exc_info=True)
            return []

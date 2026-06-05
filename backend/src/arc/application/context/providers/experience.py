"""经验上下文 Provider — 从经验库召回相关经验。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class ExperienceProvider:
    """注入与当前任务相关的历史经验。

    使用 MemoryScorer 五维打分排序，取 Top-5。
    """

    source = "experience"

    def __init__(self, db: AsyncSession):
        self._db = db
        self._injected_ids: list[uuid.UUID] = []

    @property
    def injected_experience_ids(self) -> list[uuid.UUID]:
        return self._injected_ids

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        self._injected_ids = []
        if not request.todo:
            return []

        try:
            content = await self._build(request.todo)
            if not content:
                return []
            return [ContextSegment(
                source=self.source,
                priority=1,
                content=content,
                metadata={"injected_ids": [str(i) for i in self._injected_ids]},
            )]
        except Exception:
            logger.debug("ExperienceProvider failed", exc_info=True)
            return []

    async def _build(self, todo) -> str:
        from arc.application.experience.scorer import MemoryScorer
        from arc.infrastructure.repositories.experience import ExperienceRepository

        exp_repo = ExperienceRepository(self._db)

        candidates = []
        if todo.project_id:
            project_exps = await exp_repo.list_by_project_id(
                todo.project_id, limit=20,
            )
            candidates.extend(project_exps)

        from arc.domain.todo.value_objects import ExperienceScope
        try:
            global_exps = await exp_repo.list_by_scope(
                ExperienceScope.GLOBAL, limit=10,
            )
            seen_ids = {e.id for e in candidates}
            candidates.extend(e for e in global_exps if e.id not in seen_ids)
        except Exception:
            pass

        if not candidates:
            return ""

        scorer = MemoryScorer()

        query_embedding = None
        try:
            from arc.application.ai.local_embedding import embed_local
            query_text = f"{todo.title} {todo.description or ''}"
            query_embedding = await embed_local(query_text)
        except Exception:
            pass

        scored = scorer.score_batch(candidates, query_embedding)
        top_k = scored[:5]

        parts = []
        for exp, score in top_k:
            if score < 0.2:
                continue
            self._injected_ids.append(exp.id)
            parts.append(
                f"### {exp.title} (相关度: {score:.2f})\n"
                f"**问题**: {exp.problem}\n"
                f"**方案**: {exp.solution}"
            )

        if parts:
            return "## 相关历史经验（按相关度排序）\n\n" + "\n\n".join(parts)
        return ""

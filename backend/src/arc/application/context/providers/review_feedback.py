"""评审反馈 Provider — 注入领域模型的已知缺陷和改进建议。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class ReviewFeedbackProvider:
    """注入领域模型评审发现的未解决问题。

    只注入 pending/accepted 状态（需要关注的），
    rejected/deferred 不注入避免噪音。
    """

    source = "review_feedback"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        project_id = request.project_id or (
            request.todo.project_id if request.todo else None
        )
        if not project_id:
            return []

        try:
            content = await self._build(project_id)
            if not content:
                return []

            return [ContextSegment(
                source=self.source,
                priority=1,
                content=content,
            )]
        except Exception:
            logger.debug("ReviewFeedbackProvider failed", exc_info=True)
            return []

    async def _build(self, project_id: uuid.UUID) -> str:
        from arc.domain.review.value_objects import ReviewFeedbackStatus
        from arc.infrastructure.repositories.review import ReviewFeedbackRepository

        repo = ReviewFeedbackRepository(self._db)
        pending = await repo.list_by_project(
            project_id, status=ReviewFeedbackStatus.PENDING, limit=10,
        )
        accepted = await repo.list_by_project(
            project_id, status=ReviewFeedbackStatus.ACCEPTED, limit=5,
        )
        actionable = pending + accepted
        if not actionable:
            return ""

        severity_order = {"error": 0, "warning": 1, "info": 2}
        actionable.sort(
            key=lambda f: severity_order.get(f.issue.severity.value, 9)
        )

        lines = [
            "## 领域模型已知问题（评审发现，开发时需关注）",
            "",
        ]
        for fb in actionable[:10]:
            severity_icon = {
                "error": "🔴", "warning": "🟡", "info": "ℹ️",
            }.get(fb.issue.severity.value, "·")
            status_tag = "待处理" if fb.status.value == "pending" else "已纳入计划"
            lines.append(
                f"- {severity_icon} **{fb.issue.title}** [{fb.issue.category.value}] ({status_tag})"
            )
            lines.append(f"  {fb.issue.detail}")
            if fb.issue.suggestion:
                lines.append(f"  → 建议: {fb.issue.suggestion}")

        return "\n".join(lines)

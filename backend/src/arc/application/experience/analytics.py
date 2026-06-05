"""经验引擎效果分析 — 可观测性仪表盘数据。

提供经验注入 ROI 的量化指标，回答核心问题：
1. 经验注入有没有帮到忙？（命中率）
2. 哪些经验最有价值？（top 复用）
3. 经验库健康度如何？（衰减/孤立/覆盖率）
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.models.experience import (
    Experience as ExpModel,
    ExperienceFeedback as FeedbackModel,
    ExperienceInjectionLog as InjectionLogModel,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExperienceMetrics:
    """经验引擎效果度量快照。"""

    # 注入统计
    injection_count: int = 0          # 总注入次数
    unique_experiences_injected: int = 0  # 被注入过的独立经验数
    # 效果统计
    injection_completion_rate: float = 0.0  # 注入后 todo 完成率
    positive_feedback_rate: float = 0.0     # 正面反馈占比
    # 库健康度
    total_experiences: int = 0        # 经验总数
    confirmed_count: int = 0          # 已确认的
    stale_count: int = 0              # 置信度低于阈值的
    never_reused_count: int = 0       # 从未被复用的
    # Top 复用
    top_reused: list[dict] = field(default_factory=list)


class ExperienceAnalytics:
    """经验引擎效果分析服务。"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_metrics(
        self,
        project_id: uuid.UUID | None = None,
        days: int = 30,
    ) -> ExperienceMetrics:
        """获取经验引擎效果度量。

        Args:
            project_id: 限定项目范围（None = 全局）
            days: 统计时间窗口（天）
        """
        since = datetime.now(UTC) - timedelta(days=days)

        # --- 注入统计 ---
        injection_count = await self._count_injections(project_id, since)
        unique_injected = await self._count_unique_injected(project_id, since)

        # --- 效果统计 ---
        completion_rate = await self._injection_completion_rate(project_id, since)
        feedback_rate = await self._positive_feedback_rate(project_id, since)

        # --- 库健康度 ---
        total, confirmed, stale, never_reused = await self._health_stats(project_id)

        # --- Top 复用 ---
        top_reused = await self._top_reused(project_id, limit=10)

        return ExperienceMetrics(
            injection_count=injection_count,
            unique_experiences_injected=unique_injected,
            injection_completion_rate=completion_rate,
            positive_feedback_rate=feedback_rate,
            total_experiences=total,
            confirmed_count=confirmed,
            stale_count=stale,
            never_reused_count=never_reused,
            top_reused=top_reused,
        )

    async def _count_injections(
        self, project_id: uuid.UUID | None, since: datetime,
    ) -> int:
        """指定时间窗口内的注入总次数。"""
        stmt = select(func.count()).select_from(InjectionLogModel).where(
            InjectionLogModel.created_at >= since,
        )
        if project_id:
            exp_ids = select(ExpModel.id).where(ExpModel.project_id == project_id)
            stmt = stmt.where(InjectionLogModel.experience_id.in_(exp_ids))
        result = await self._db.execute(stmt)
        return result.scalar() or 0

    async def _count_unique_injected(
        self, project_id: uuid.UUID | None, since: datetime,
    ) -> int:
        """被注入过的独立经验数。"""
        stmt = select(func.count(func.distinct(InjectionLogModel.experience_id))).where(
            InjectionLogModel.created_at >= since,
        )
        if project_id:
            exp_ids = select(ExpModel.id).where(ExpModel.project_id == project_id)
            stmt = stmt.where(InjectionLogModel.experience_id.in_(exp_ids))
        result = await self._db.execute(stmt)
        return result.scalar() or 0

    async def _injection_completion_rate(
        self, project_id: uuid.UUID | None, since: datetime,
    ) -> float:
        """注入后 todo 完成率 = completed / total_injections_with_outcome。"""
        base = select(InjectionLogModel).where(
            InjectionLogModel.created_at >= since,
            InjectionLogModel.todo_completed.isnot(None),
        )
        if project_id:
            exp_ids = select(ExpModel.id).where(ExpModel.project_id == project_id)
            base = base.where(InjectionLogModel.experience_id.in_(exp_ids))

        total_stmt = select(func.count()).select_from(base.subquery())
        completed_stmt = select(func.count()).select_from(
            base.where(InjectionLogModel.todo_completed.is_(True)).subquery()
        )

        total = (await self._db.execute(total_stmt)).scalar() or 0
        completed = (await self._db.execute(completed_stmt)).scalar() or 0

        return round(completed / total, 4) if total > 0 else 0.0

    async def _positive_feedback_rate(
        self, project_id: uuid.UUID | None, since: datetime,
    ) -> float:
        """正面反馈率 = positive / total_with_feedback。"""
        base = select(FeedbackModel).where(
            FeedbackModel.created_at >= since,
        )
        if project_id:
            exp_ids = select(ExpModel.id).where(ExpModel.project_id == project_id)
            base = base.where(FeedbackModel.experience_id.in_(exp_ids))

        total_stmt = select(func.count()).select_from(base.subquery())
        positive_stmt = select(func.count()).select_from(
            base.where(FeedbackModel.helpful.is_(True)).subquery()
        )

        total = (await self._db.execute(total_stmt)).scalar() or 0
        positive = (await self._db.execute(positive_stmt)).scalar() or 0

        return round(positive / total, 4) if total > 0 else 0.0

    async def _health_stats(
        self, project_id: uuid.UUID | None,
    ) -> tuple[int, int, int, int]:
        """库健康度: (total, confirmed, stale, never_reused)。"""
        base = select(ExpModel)
        if project_id:
            base = base.where(ExpModel.project_id == project_id)

        total = (await self._db.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar() or 0

        confirmed = (await self._db.execute(
            select(func.count()).select_from(
                base.where(ExpModel.status == "confirmed").subquery()
            )
        )).scalar() or 0

        stale = (await self._db.execute(
            select(func.count()).select_from(
                base.where(ExpModel.confidence < 0.3).subquery()
            )
        )).scalar() or 0

        never_reused = (await self._db.execute(
            select(func.count()).select_from(
                base.where(ExpModel.reuse_count == 0).subquery()
            )
        )).scalar() or 0

        return total, confirmed, stale, never_reused

    async def _top_reused(
        self, project_id: uuid.UUID | None, limit: int = 10,
    ) -> list[dict]:
        """最常被复用的经验 top N。"""
        stmt = (
            select(ExpModel.id, ExpModel.title, ExpModel.reuse_count, ExpModel.confidence)
            .where(ExpModel.reuse_count > 0)
        )
        if project_id:
            stmt = stmt.where(ExpModel.project_id == project_id)
        stmt = stmt.order_by(ExpModel.reuse_count.desc()).limit(limit)

        result = await self._db.execute(stmt)
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "reuse_count": row.reuse_count,
                "confidence": round(row.confidence, 3),
            }
            for row in result.all()
        ]

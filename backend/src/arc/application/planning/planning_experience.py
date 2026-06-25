"""版本规划经验提取 — 从版本发布和范围变更中沉淀经验。"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.experience.entity import Experience
from arc.domain.planning.entity import PlanningSession
from arc.domain.todo.value_objects import (
    ExperienceCategory,
    ExperienceSource,
    TodoStatus,
)
from arc.infrastructure.repositories.experience import ExperienceRepository
from arc.infrastructure.repositories.planning import PlanningSessionRepository
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


class PlanningExperienceService:
    """版本规划经验提取服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_scope_change(
        self,
        session: PlanningSession,
        abandon_todo_ids: list[uuid.UUID],
    ) -> None:
        """记录范围变更经验。"""
        todo_repo = TodoRepository(self.db)
        abandoned_todos = []
        for tid in abandon_todo_ids:
            t = await todo_repo.get_by_id(tid)
            if t:
                abandoned_todos.append(t)
        titles = [t.title for t in abandoned_todos]

        roadmap = session.roadmap or {}
        original_count = sum(len(v.get("features", [])) for v in roadmap.get("versions", []))

        truncated = ", ".join(titles[:5])
        if len(titles) > 5:
            truncated += f" 等共 {len(titles)} 项"

        exp = Experience(
            project_id=session.project_id,
            version_id=session.version_id,
            category=ExperienceCategory.SCOPE_CHANGE,
            source=ExperienceSource.SCOPE_CHANGE,
            title=f"范围变更：废弃 {len(titles)} 个需求",
            problem=f"原规划 {original_count} 个功能点，执行中发现部分需求需要调整",
            solution=f"废弃: {truncated}",
            decisions=["聚焦核心交付，砍掉非关键项"],
            pitfalls=[],
            applicable_scenarios="迭代中期范围收窄",
            confidence=0.6,
        )
        try:
            await ExperienceRepository(self.db).create(exp)
        except Exception as exc:
            logger.warning("Failed to record scope change experience: %s", exc)

    async def extract_release_experience(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """版本发布时提取估算校准经验。"""
        version_repo = VersionRepository(self.db)
        todo_repo = TodoRepository(self.db)
        session_repo = PlanningSessionRepository(self.db)

        version = await version_repo.get_by_id(version_id)
        if not version:
            return

        todos, _ = await todo_repo.list_all(version_id=version_id, limit=500)
        if not todos:
            return

        done_count = sum(1 for t in todos if t.status == TodoStatus.DONE)
        abandoned_count = sum(1 for t in todos if t.status == TodoStatus.ABANDONED)
        total = len(todos)

        sessions = await session_repo.list_by_version(version_id)
        planned_count = 0
        if sessions:
            roadmap = sessions[0].roadmap or {}
            planned_count = sum(len(v.get("features", [])) for v in roadmap.get("versions", []))

        completion_rate = done_count / total if total > 0 else 0

        exp = Experience(
            project_id=project_id,
            version_id=version_id,
            category=ExperienceCategory.ESTIMATION,
            source=ExperienceSource.VERSION_RELEASE,
            title=f"版本 {version.name} 交付偏差",
            problem=f"规划 {planned_count} 项，实际交付 {done_count} 项"
            + (f"，废弃 {abandoned_count} 项" if abandoned_count else ""),
            solution=f"完成率 {completion_rate:.0%}，总计 {total} 项需求",
            decisions=[],
            pitfalls=[],
            applicable_scenarios=f"类似规模({max(planned_count, total)}项)版本的规划参考",
            confidence=0.7,
        )
        try:
            await ExperienceRepository(self.db).create(exp)
        except Exception as exc:
            logger.warning("Failed to record release experience: %s", exc)

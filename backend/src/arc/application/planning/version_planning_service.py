"""版本规划相关服务 — 从 PlanningService 提取的 version planning 方法。

包含 scope diff、re-apply、经验提取等版本级操作。
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.experience.entity import Experience
from arc.domain.planning.entity import PlanningSession
from arc.domain.planning.value_objects import PlanningStatus
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import (
    ExperienceCategory,
    ExperienceSource,
    TodoStatus,
)
from arc.infrastructure.repositories.planning import PlanningSessionRepository
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


def _feature_key(title: str) -> str:
    """生成 feature 的稳定标识，用于 diff 匹配。"""
    return title.strip().lower()[:200]


def _extract_all_features_from_data(versions_data: list[dict]) -> list[dict]:
    """从 versions_data 中提取所有 features。"""
    features = []
    for v_data in versions_data:
        features.extend(v_data.get("features", []))
    if not features:
        features = [v for v in versions_data if v.get("title")]
    return features


def _extract_all_features(roadmap: dict) -> list[dict]:
    return _extract_all_features_from_data(roadmap.get("versions", []))


class VersionPlanningService:
    """版本级规划操作：scope diff、re-apply、经验记录。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = PlanningSessionRepository(db)
        self.version_repo = VersionRepository(db)
        self.todo_repo = TodoRepository(db)

    async def preview_apply_diff(self, session_id: uuid.UUID) -> dict:
        """计算 re-apply 时的范围变更 diff。"""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise ValueError("路线图尚未确认")

        existing_todos = await self.todo_repo.list_by_session(session_id)
        if not existing_todos:
            return {"is_first_apply": True}

        new_features = _extract_all_features(session.roadmap or {})
        existing_map = {
            t.source_feature_key: t
            for t in existing_todos
            if t.source_feature_key and t.status != TodoStatus.ABANDONED
        }
        new_map = {_feature_key(f["title"]): f for f in new_features if f.get("title")}

        added = [f for k, f in new_map.items() if k not in existing_map]
        removed = [t for k, t in existing_map.items() if k not in new_map]

        return {
            "is_first_apply": False,
            "added": [
                {"title": f.get("title", ""), "complexity": f.get("complexity")}
                for f in added
            ],
            "removed_active": [
                {"id": str(t.id), "title": t.title}
                for t in removed
                if t.status == TodoStatus.ACTIVE
            ],
            "removed_pending": [
                {"id": str(t.id), "title": t.title}
                for t in removed
                if t.status == TodoStatus.PENDING
            ],
            "removed_done": [
                {"id": str(t.id), "title": t.title}
                for t in removed
                if t.status == TodoStatus.DONE
            ],
            "unchanged_count": len(existing_map) - len(removed),
        }

    async def apply_with_diff(
        self,
        session_id: uuid.UUID,
        abandon_todo_ids: list[uuid.UUID],
    ) -> dict:
        """带 diff 的 re-apply：废弃指定 Todos，只创建新增的。"""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError("Session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise ValueError("路线图尚未确认")

        for tid in abandon_todo_ids:
            todo = await self.todo_repo.get_by_id(tid)
            if todo:
                todo.abandon()
                await self.todo_repo.update(todo)

        existing_keys = {
            t.source_feature_key
            for t in await self.todo_repo.list_by_session(session_id)
            if t.source_feature_key and t.status != TodoStatus.ABANDONED
        }
        new_features = _extract_all_features(session.roadmap or {})
        created_count = 0
        for feat in new_features:
            title = feat.get("title", "")
            if not title:
                continue
            key = _feature_key(title)
            if key not in existing_keys:
                todo = Todo(
                    title=title,
                    description=feat.get("description", ""),
                    project_id=session.project_id,
                    version_id=session.version_id,
                    priority=feat.get("priority", 2),
                    source_session_id=session.id,
                    source_feature_key=key,
                )
                await self.todo_repo.create(todo)
                created_count += 1

        if abandon_todo_ids:
            await self._record_scope_change_experience(session, abandon_todo_ids)

        session.apply()
        await self.session_repo.update(session)
        return {
            "message": f"已创建 {created_count} 个新需求，废弃 {len(abandon_todo_ids)} 个",
            "created_count": created_count,
            "abandoned_count": len(abandon_todo_ids),
        }

    async def extract_release_experience(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """版本发布时提取估算校准经验。"""
        from arc.infrastructure.repositories.experience import ExperienceRepository

        version = await self.version_repo.get_by_id(version_id)
        if not version:
            return

        todos, _ = await self.todo_repo.list_all(version_id=version_id, limit=500)
        if not todos:
            return

        done_count = sum(1 for t in todos if t.status == TodoStatus.DONE)
        abandoned_count = sum(1 for t in todos if t.status == TodoStatus.ABANDONED)
        total = len(todos)

        sessions = await self.session_repo.list_by_version(version_id)
        planned_count = 0
        if sessions:
            roadmap = sessions[0].roadmap or {}
            planned_count = sum(
                len(v.get("features", [])) for v in roadmap.get("versions", [])
            )

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

    async def _record_scope_change_experience(
        self,
        session: PlanningSession,
        abandon_todo_ids: list[uuid.UUID],
    ) -> None:
        """记录范围变更经验。"""
        from arc.infrastructure.repositories.experience import ExperienceRepository

        abandoned_todos = []
        for tid in abandon_todo_ids:
            t = await self.todo_repo.get_by_id(tid)
            if t:
                abandoned_todos.append(t)
        titles = [t.title for t in abandoned_todos]

        roadmap = session.roadmap or {}
        original_count = sum(
            len(v.get("features", [])) for v in roadmap.get("versions", [])
        )

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

"""版本规划引擎 — 从文档/约束条件生成版本路线图。"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.domain.conversation.entity import Conversation
from arc.domain.errors import AppError, NotFoundError
from arc.domain.planning.entity import PlanningSession
from arc.domain.planning.value_objects import PlanningStatus
from arc.domain.project.entity import Version
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import (
    ConversationPurpose,
    MessageRole,
    TodoStatus,
)
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.planning import (
    DocumentRepository,
    PlanningSessionRepository,
)
from arc.infrastructure.repositories.project import ProjectRepository, VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


PLANNING_SYSTEM_PROMPT = """\
将以下功能需求规划为版本路线图。

约束条件：
{constraints}

{experience_context}

{domain_model_context}

功能清单：
{features}

输出 JSON:
```json
{{
  "strategy": "选择的策略",
  "strategy_rationale": "为什么选这个策略",
  "versions": [
    {{
      "name": "版本号",
      "goal": "版本目标（用户视角）",
      "scope_rationale": "为什么这些功能在这个版本",
      "features": [
        {{"title": "", "complexity": "S/M/L/XL", "priority": 1}}
      ],
      "estimated_sprints": 2,
      "risks": [],
      "dependencies": []
    }}
  ],
  "timeline_mermaid": "gantt Mermaid 代码",
  "total_estimated_weeks": 12
}}
```"""


ITERATION_REVIEW_PROMPT = """分析当前迭代状态，评估进展并给出行动建议。

## 当前版本
版本: {version_name}
目标: {version_goal}

{project_context}

## 需求状态
{todo_status_summary}

输出简洁的分析报告（Markdown）。"""


def _feature_key(title: str) -> str:
    """生成 feature 的稳定标识，用于 diff 匹配。"""
    return title.strip().lower()[:200]


class PlanningService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = PlanningSessionRepository(db)
        self.doc_repo = DocumentRepository(db)
        self.project_repo = ProjectRepository(db)
        self.version_repo = VersionRepository(db)
        self.todo_repo = TodoRepository(db)
        self.conv_repo = ConversationRepository(db)

    async def create_session(
        self,
        project_id: uuid.UUID,
        document_ids: list[uuid.UUID] | None = None,
        constraints: dict | None = None,
        version_id: uuid.UUID | None = None,
    ) -> PlanningSession:
        session = PlanningSession(
            project_id=project_id,
            version_id=version_id,
            document_ids=document_ids or [],
            constraints=constraints or {},
        )

        conv = Conversation(
            todo_id=project_id,
            purpose=ConversationPurpose.PLANNING,
        )
        conv.add_message(
            role=MessageRole.SYSTEM,
            content="版本规划会话已启动。",
        )
        await self.conv_repo.create(conv)
        session.conversation_id = conv.id

        await self.session_repo.create(session)
        return session

    async def generate_roadmap(self, session_id: uuid.UUID) -> dict:
        """根据文档和约束条件生成版本路线图。"""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")

        features = await self._collect_features(session)
        constraints_text = self._format_constraints(session.constraints)
        features_text = json.dumps(features, ensure_ascii=False, indent=2)

        # T1: 注入历史经验 — 让规划不再从零开始
        experience_context = await self._build_planning_experience_context(
            session.project_id
        )

        # T2: 注入领域模型 — 让规划理解架构现实
        domain_model_context = await self._build_domain_model_context(
            session.project_id
        )

        prompt = PLANNING_SYSTEM_PROMPT.format(
            constraints=constraints_text,
            features=features_text,
            experience_context=experience_context,
            domain_model_context=domain_model_context,
        )

        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat([LLMMessage(role="user", content=prompt)])
        finally:
            await adapter.close()

        roadmap = extract_json(response.content)
        if not isinstance(roadmap, dict):
            roadmap = {"raw_response": response.content, "parse_error": True}

        session.submit_for_review(roadmap)
        await self.session_repo.update(session)

        if session.conversation_id:
            conv = await self.conv_repo.get_by_id(session.conversation_id)
            if conv:
                roadmap_json = json.dumps(
                    roadmap, ensure_ascii=False, indent=2
                )
                conv.add_message(
                    role=MessageRole.ASSISTANT,
                    content=f"已生成版本路线图：\n```json\n{roadmap_json}\n```",
                )
                await self.conv_repo.add_message(conv.id, conv.messages[-1])

        return roadmap

    async def apply_roadmap(self, session_id: uuid.UUID) -> list[Version]:
        """将确认的路线图转化为实际的Version和Todo。"""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError("Planning session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise AppError("路线图尚未确认，无法应用")

        roadmap = session.roadmap
        versions_data = roadmap.get("versions", [])

        if session.version_id:
            return await self._apply_to_version(session, versions_data)
        return await self._apply_create_versions(session, versions_data)

    async def _apply_to_version(
        self,
        session: PlanningSession,
        versions_data: list[dict],
    ) -> list[Version]:
        """版本级规划：在指定Version下创建Todos。"""
        version = await self.version_repo.get_by_id(session.version_id)
        if not version:
            raise NotFoundError("目标版本不存在")

        features = self._extract_all_features_from_data(versions_data)

        for feat in features:
            title = feat.get("title", "")
            if not title:
                continue
            todo = Todo(
                title=title,
                description=feat.get("description", ""),
                project_id=session.project_id,
                version_id=session.version_id,
                priority=feat.get("priority", 2),
                source_session_id=session.id,
                source_feature_key=_feature_key(title),
            )
            await self.todo_repo.create(todo)

        session.apply()
        await self.session_repo.update(session)
        return [version]

    async def _apply_create_versions(
        self,
        session: PlanningSession,
        versions_data: list[dict],
    ) -> list[Version]:
        """全局规划：创建多个Version + Todos。"""
        if not versions_data:
            raise AppError("路线图中没有版本数据")

        created_versions = []
        for i, v_data in enumerate(versions_data):
            version = Version(
                project_id=session.project_id,
                name=v_data.get("name", f"v{i + 1}"),
                goal=v_data.get("goal", ""),
                order=i + 1,
            )
            version = await self.version_repo.create(version)

            for feat in v_data.get("features", []):
                title = feat.get("title", "")
                if not title:
                    continue
                todo = Todo(
                    title=title,
                    description=feat.get("description", ""),
                    project_id=session.project_id,
                    version_id=version.id,
                    priority=feat.get("priority", 2),
                    source_session_id=session.id,
                    source_feature_key=_feature_key(title),
                )
                await self.todo_repo.create(todo)

            created_versions.append(version)

        session.apply()
        await self.session_repo.update(session)
        return created_versions

    # ── Scope diff ───────────────────────────────────────

    @staticmethod
    def _extract_all_features_from_data(versions_data: list[dict]) -> list[dict]:
        features = []
        for v_data in versions_data:
            features.extend(v_data.get("features", []))
        if not features:
            features = [v for v in versions_data if v.get("title")]
        return features

    def _extract_all_features(self, roadmap: dict) -> list[dict]:
        return self._extract_all_features_from_data(roadmap.get("versions", []))

    async def preview_apply_diff(self, session_id: uuid.UUID) -> dict:
        """计算 re-apply 时的范围变更 diff。"""
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise NotFoundError("Session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise AppError("路线图尚未确认")

        existing_todos = await self.todo_repo.list_by_session(session_id)
        if not existing_todos:
            return {"is_first_apply": True}

        new_features = self._extract_all_features(session.roadmap or {})
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
                {"title": f.get("title", ""), "complexity": f.get("complexity")} for f in added
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
                {"id": str(t.id), "title": t.title} for t in removed if t.status == TodoStatus.DONE
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
            raise NotFoundError("Session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise AppError("路线图尚未确认")

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
        new_features = self._extract_all_features(session.roadmap or {})
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

    async def _record_scope_change_experience(
        self,
        session: PlanningSession,
        abandon_todo_ids: list[uuid.UUID],
    ) -> None:
        """记录范围变更经验 — 委托给 PlanningExperienceService。"""
        from arc.application.planning.planning_experience import PlanningExperienceService

        await PlanningExperienceService(self.db).record_scope_change(session, abandon_todo_ids)

    async def extract_release_experience(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> None:
        """版本发布时提取估算校准经验 — 委托给 PlanningExperienceService。"""
        from arc.application.planning.planning_experience import PlanningExperienceService

        await PlanningExperienceService(self.db).extract_release_experience(project_id, version_id)

    async def _collect_features(self, session: PlanningSession) -> list[dict]:
        """汇总所有关联文档中解析出的功能点。"""
        all_features = []
        for doc_id in session.document_ids:
            doc = await self.doc_repo.get_by_id(doc_id)
            if doc and doc.parsed_features:
                all_features.extend(doc.parsed_features)

        if not all_features:
            existing_todos, _ = await self.todo_repo.list_all(
                project_id=session.project_id,
                limit=500,
            )
            for t in existing_todos:
                all_features.append(
                    {
                        "title": t.title,
                        "description": t.description,
                        "complexity": "M",
                        "priority_hint": "medium",
                    }
                )

        return all_features

    @staticmethod
    def _format_constraints(constraints: dict) -> str:
        from arc.application.planning.planning_context import format_constraints
        return format_constraints(constraints)

    async def _build_planning_experience_context(
        self, project_id: uuid.UUID
    ) -> str:
        from arc.application.planning.planning_context import (
            build_planning_experience_context,
        )
        return await build_planning_experience_context(self.db, project_id)

    async def _build_domain_model_context(self, project_id: uuid.UUID) -> str:
        from arc.application.planning.planning_context import (
            build_domain_model_context,
        )
        return await build_domain_model_context(self.db, project_id)

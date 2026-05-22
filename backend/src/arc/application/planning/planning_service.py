"""版本规划引擎 — 从文档/约束条件生成版本路线图。"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.domain.conversation.entity import Conversation
from arc.domain.experience.entity import Experience
from arc.domain.planning.entity import PlanningSession
from arc.domain.planning.value_objects import PlanningStatus
from arc.domain.project.entity import Version
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import (
    ConversationPurpose,
    ExperienceCategory,
    ExperienceSource,
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
你是一位资深产品经理 + 技术项目经理，负责将功能需求拆分为合理的版本路线图。

## 你的规划方法论
1. **理解全貌**：先理清所有功能点及其依赖关系
2. **确定策略**：根据约束条件选择最优的版本切分策略
3. **版本切分**：每个版本必须有独立的用户价值（能讲出一个完整故事）
4. **容量校验**：每个版本的工作量必须在约束范围内
5. **风险前置**：高风险功能放在前面验证

## 切分策略选项
- **MVP优先**：第一个版本只做最小可行产品，快速验证
- **模块优先**：按业务模块分期交付，每期完成一个完整模块
- **风险驱动**：技术风险高的先做，降低后期不确定性

## 约束条件
{constraints}

## 功能清单
{features}

## 输出要求
产出严格JSON格式的版本路线图：
```json
{{
  "strategy": "选择的策略名称",
  "strategy_rationale": "为什么选择这个策略（结合项目特点说明）",
  "versions": [
    {{
      "name": "版本号和代号",
      "goal": "版本目标（一句话，用户视角）",
      "scope_rationale": "为什么把这些功能放在这个版本（不超过2句话）",
      "features": [
        {{
          "title": "功能名称",
          "complexity": "S/M/L/XL",
          "priority": 1
        }}
      ],
      "estimated_sprints": 2,
      "risks": ["风险项"],
      "dependencies": ["依赖的前序版本"]
    }}
  ],
  "timeline_mermaid": "gantt图的Mermaid代码",
  "total_estimated_weeks": 12
}}
```

重要：
- 每个版本必须有独立的用户价值，不能出现"做了半个功能"的版本
- estimated_sprints基于约束条件中的迭代周期和人力计算
- 如果功能点太多，可以建议合理的分期数量
- timeline_mermaid必须是可直接渲染的Mermaid gantt语法"""


ITERATION_REVIEW_PROMPT = """你是一位敏捷教练，负责分析当前迭代状态并给出下一步建议。

## 当前版本信息
版本: {version_name}
目标: {version_goal}

## 需求状态
{todo_status_summary}

## 分析要求
1. 本迭代进展评估（按时/延期/提前）
2. 阻塞项识别和建议
3. 下个迭代需求推荐（从backlog中选择）
4. 版本目标完整性检查（当前进度是否在版本目标轨道上）
5. 风险预警

输出简洁的分析报告，用markdown格式。"""


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
            raise ValueError("Planning session not found")

        features = await self._collect_features(session)
        constraints_text = self._format_constraints(session.constraints)
        features_text = json.dumps(features, ensure_ascii=False, indent=2)

        prompt = PLANNING_SYSTEM_PROMPT.format(
            constraints=constraints_text,
            features=features_text,
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
            raise ValueError("Planning session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise ValueError("路线图尚未确认，无法应用")

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
            raise ValueError("目标版本不存在")

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
            raise ValueError("路线图中没有版本数据")

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

    async def analyze_iteration(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> str:
        """分析当前迭代状态并给出建议。"""
        version = await self.version_repo.get_by_id(version_id)
        if not version:
            raise ValueError("版本不存在")

        todos, _ = await self.todo_repo.list_all(version_id=version_id, limit=1000)
        status_summary = self._format_todo_status(todos)

        prompt = ITERATION_REVIEW_PROMPT.format(
            version_name=version.name,
            version_goal=version.goal,
            todo_status_summary=status_summary,
        )

        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat([LLMMessage(role="user", content=prompt)])
        finally:
            await adapter.close()

        return response.content

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
            raise ValueError("Session not found")
        if session.status != PlanningStatus.CONFIRMED:
            raise ValueError("路线图尚未确认")

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
        """记录范围变更经验。"""
        from arc.infrastructure.repositories.experience import ExperienceRepository

        abandoned_todos = []
        for tid in abandon_todo_ids:
            t = await self.todo_repo.get_by_id(tid)
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
        if not constraints:
            return "无特定约束，使用合理默认值（2周迭代，3人团队）"
        parts = []
        if "team_capacity" in constraints:
            parts.append(f"- 团队规模: {constraints['team_capacity']}人")
        if "iteration_weeks" in constraints:
            parts.append(f"- 迭代周期: {constraints['iteration_weeks']}周/迭代")
        if "hard_deadlines" in constraints:
            for dl in constraints["hard_deadlines"]:
                parts.append(f"- 硬截止: {dl}")
        if "release_strategy" in constraints:
            parts.append(f"- 发布策略偏好: {constraints['release_strategy']}")
        if "priority_framework" in constraints:
            parts.append(f"- 优先级框架: {constraints['priority_framework']}")
        return "\n".join(parts) if parts else "无特定约束"

    @staticmethod
    def _format_todo_status(todos: list) -> str:
        if not todos:
            return "暂无需求"
        lines = []
        for t in todos:
            status_label = {
                "pending": "待启动",
                "active": "进行中",
                "done": "已完成",
                "error": "异常",
            }.get(t.status.value, t.status.value)
            phase_label = f" [{t.current_phase.value}]" if t.current_phase else ""
            lines.append(f"- [{status_label}]{phase_label} {t.title}")
        return "\n".join(lines)

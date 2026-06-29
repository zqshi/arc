from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.capability.value_objects import ToolSpec
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """Assembled context sent to a coding agent for execution."""

    todo_id: str
    todo_title: str
    todo_description: str = ""
    project_context: str = ""
    requirement_spec: dict = field(default_factory=dict)
    ui_design: dict = field(default_factory=dict)
    tech_architecture: dict = field(default_factory=dict)
    dev_report: dict = field(default_factory=dict)
    test_report: dict = field(default_factory=dict)
    related_experiences: list[dict] = field(default_factory=list)
    # v6.17: 本环节 skill 注入 (规范文本 + 工具集), 由 CapabilityProvider.load_phase_skills 填充
    skill_specs: list[str] = field(default_factory=list)
    tool_specs: list[ToolSpec] = field(default_factory=list)
    # v6.17: MCP server 连接配置 (供 ClaudeCode/OpenHands 注入 --mcp-config/runtime)
    mcp_servers: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts = [f"# {self.todo_title}", ""]
        if self.todo_description:
            parts.append(f"## 描述\n{self.todo_description}\n")

        if self.project_context:
            parts.append(self.project_context)
            parts.append("")

        if self.requirement_spec:
            parts.append("## 需求规格")
            for key, val in self.requirement_spec.items():
                if key.startswith("_"):
                    continue
                val_str = val if isinstance(val, str) else json.dumps(
                    val, ensure_ascii=False
                )
                parts.append(f"### {key}\n{val_str}\n")

        if self.ui_design:
            parts.append("## UI设计")
            flow = self.ui_design.get("flow_diagram", "")
            if flow:
                parts.append(f"### 用户流程\n```mermaid\n{flow}\n```\n")
            wires = self.ui_design.get("wireframes", [])
            for w in wires:
                if isinstance(w, dict):
                    parts.append(f"### {w.get('page_name', '页面')}\n{w.get('description', '')}\n")

        if self.tech_architecture:
            parts.append("## 技术架构")
            for key, val in self.tech_architecture.items():
                if key.startswith("_"):
                    continue
                val_str = val if isinstance(val, str) else json.dumps(
                    val, ensure_ascii=False
                )
                parts.append(f"### {key}\n{val_str}\n")

        if self.dev_report:
            parts.append("## 开发报告")
            parts.append(json.dumps(self.dev_report, ensure_ascii=False, indent=2))

        if self.test_report:
            parts.append("## 测试报告")
            parts.append(json.dumps(self.test_report, ensure_ascii=False, indent=2))

        if self.related_experiences:
            parts.append("## 相关历史经验")
            for i, exp in enumerate(self.related_experiences, 1):
                parts.append(f"### 经验{i}: {exp.get('title', '')}")
                if exp.get("problem"):
                    parts.append(f"**问题**: {exp['problem']}")
                if exp.get("solution"):
                    parts.append(f"**方案**: {exp['solution']}")
                if exp.get("pitfalls"):
                    parts.append(f"**踩坑**: {'; '.join(exp['pitfalls'])}")
                parts.append("")

        # v6.17: 本环节技能规范 — skill 规范文本 (所有 adapter 经 to_markdown 生效)
        if self.skill_specs:
            parts.append("## 本环节技能规范")
            for spec in self.skill_specs:
                parts.append(spec)
                parts.append("")

        # v6.17: 本环节启用工具 — OpenHands/Claude Code 转指引文本;
        # Codex 额外注册 function (见 CodexAdapter.start, T3)
        if self.tool_specs:
            parts.append("## 本环节启用工具")
            for tool in self.tool_specs:
                source_tag = "mcp" if tool.is_mcp else "inline"
                detail = f" → {tool.server_ref}" if tool.is_mcp else ""
                parts.append(
                    f"- **{tool.name}** ({source_tag}): {tool.description}{detail}"
                )
            parts.append("按上述工具规范执行任务。")
            parts.append("")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "todo_id": self.todo_id,
            "todo_title": self.todo_title,
            "todo_description": self.todo_description,
            "requirement_spec": self.requirement_spec,
            "ui_design": self.ui_design,
            "tech_architecture": self.tech_architecture,
            "dev_report": self.dev_report,
            "test_report": self.test_report,
            "related_experiences": self.related_experiences,
            "skill_specs": self.skill_specs,
            "tool_specs": [
                {
                    "name": t.name,
                    "description": t.description,
                    "source": t.source.value,
                    "parameters": t.parameters,
                    "server_ref": t.server_ref,
                }
                for t in self.tool_specs
            ],
            "mcp_servers": self.mcp_servers,
        }


class TaskContextBuilder:
    """Builds TaskContext from confirmed artifacts in the database."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.artifact_repo = ArtifactRepository(db)

    async def build(
        self, todo_id: uuid.UUID, phase_type: str | None = None
    ) -> TaskContext:
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        from arc.application.context.provider import ProjectContextProvider

        project_provider = ProjectContextProvider(self.db)
        project_ctx = await project_provider.get_context(todo_id)

        confirmed = await self.artifact_repo.list_confirmed_by_todo(todo_id)
        artifact_map: dict[str, dict] = {}
        for a in confirmed:
            at = a.artifact_type if isinstance(a.artifact_type, str) else a.artifact_type.value
            content = a.content or {}
            filtered = {k: v for k, v in content.items() if not k.startswith("_meta")}
            artifact_map[at] = filtered

        experiences = await self._fetch_related_experiences(todo)

        # 注入评审反馈 — Agent 也需要知道领域模型的已知缺陷
        agent_section = project_ctx.to_agent_section()
        if todo.project_id:
            review_section = await self._build_review_feedback(todo.project_id)
            if review_section:
                agent_section = agent_section + "\n\n" + review_section

        # v6.17: 注入本环节 skill 规范 + 工具集 + MCP server 配置
        # (CapabilityProvider 单一真相源, 与对话侧 provide 共享 _collect_active_caps)
        skill_specs: list[str] = []
        tool_specs: list[ToolSpec] = []
        mcp_servers: list[dict] = []
        if phase_type and todo.project_id:
            from arc.application.context.providers.capability import CapabilityProvider

            prompts, tools, servers = await CapabilityProvider(self.db).load_phase_skills(
                todo.project_id, phase_type
            )
            skill_specs = prompts
            tool_specs = tools
            mcp_servers = servers

        return TaskContext(
            todo_id=str(todo_id),
            todo_title=todo.title,
            todo_description=todo.description or "",
            project_context=agent_section,
            requirement_spec=artifact_map.get(ArtifactType.REQUIREMENT_SPEC, {}),
            ui_design=artifact_map.get(ArtifactType.UI_DESIGN, {}),
            tech_architecture=artifact_map.get(ArtifactType.TECH_ARCHITECTURE, {}),
            dev_report=artifact_map.get(ArtifactType.DEV_REPORT, {}),
            test_report=artifact_map.get(ArtifactType.TEST_REPORT, {}),
            related_experiences=experiences,
            skill_specs=skill_specs,
            tool_specs=tool_specs,
            mcp_servers=mcp_servers,
        )

    async def _fetch_related_experiences(self, todo) -> list[dict]:
        try:
            from arc.application.experience.service import ExperienceService

            exp_svc = ExperienceService(self.db)
            exps = await exp_svc.search_similar(
                f"{todo.title} {todo.description or ''}",
                limit=3,
                project_id=todo.project_id,
            )
            return [
                {
                    "title": e.title,
                    "problem": e.problem,
                    "solution": e.solution,
                    "pitfalls": e.pitfalls,
                    "decisions": e.decisions,
                }
                for e in exps
            ]
        except Exception as exc:
            logger.warning("Failed to fetch related experiences: %s", exc)
            return []

    async def _build_review_feedback(self, project_id: uuid.UUID) -> str:
        """构建评审反馈摘要，注入 Agent 上下文。"""
        try:
            from arc.domain.review.value_objects import ReviewFeedbackStatus
            from arc.infrastructure.repositories.review import ReviewFeedbackRepository

            repo = ReviewFeedbackRepository(self.db)
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

            lines = ["## 领域模型已知问题（评审发现，开发时需关注）", ""]
            for fb in actionable[:10]:
                severity_icon = {
                    "error": "🔴", "warning": "🟡", "info": "ℹ️",
                }.get(fb.issue.severity.value, "·")
                lines.append(
                    f"- {severity_icon} **{fb.issue.title}** [{fb.issue.category.value}]"
                )
                lines.append(f"  {fb.issue.detail}")
                if fb.issue.suggestion:
                    lines.append(f"  → 建议: {fb.issue.suggestion}")

            return "\n".join(lines)
        except Exception:
            logger.debug("Failed to build review feedback for agent context", exc_info=True)
            return ""

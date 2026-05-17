from __future__ import annotations

import json
import logging
import uuid

from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """Assembled context sent to a coding agent for execution."""

    todo_id: str
    todo_title: str
    todo_description: str = ""
    requirement_spec: dict = field(default_factory=dict)
    ui_design: dict = field(default_factory=dict)
    tech_architecture: dict = field(default_factory=dict)
    dev_report: dict = field(default_factory=dict)
    test_report: dict = field(default_factory=dict)
    related_experiences: list[dict] = field(default_factory=list)

    def to_markdown(self) -> str:
        parts = [f"# {self.todo_title}", ""]
        if self.todo_description:
            parts.append(f"## 描述\n{self.todo_description}\n")

        if self.requirement_spec:
            parts.append("## 需求规格")
            for key, val in self.requirement_spec.items():
                if key.startswith("_"):
                    continue
                parts.append(f"### {key}\n{val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)}\n")

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
                parts.append(f"### {key}\n{val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)}\n")

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
        }


class TaskContextBuilder:
    """Builds TaskContext from confirmed artifacts in the database."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.artifact_repo = ArtifactRepository(db)

    async def build(self, todo_id: uuid.UUID) -> TaskContext:
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        confirmed = await self.artifact_repo.list_confirmed_by_todo(todo_id)
        artifact_map: dict[str, dict] = {}
        for a in confirmed:
            at = a.artifact_type if isinstance(a.artifact_type, str) else a.artifact_type.value
            content = a.content or {}
            filtered = {k: v for k, v in content.items() if not k.startswith("_meta")}
            artifact_map[at] = filtered

        experiences = await self._fetch_related_experiences(todo)

        return TaskContext(
            todo_id=str(todo_id),
            todo_title=todo.title,
            todo_description=todo.description or "",
            requirement_spec=artifact_map.get(ArtifactType.REQUIREMENT_SPEC, {}),
            ui_design=artifact_map.get(ArtifactType.UI_DESIGN, {}),
            tech_architecture=artifact_map.get(ArtifactType.TECH_ARCHITECTURE, {}),
            dev_report=artifact_map.get(ArtifactType.DEV_REPORT, {}),
            test_report=artifact_map.get(ArtifactType.TEST_REPORT, {}),
            related_experiences=experiences,
        )

    async def _fetch_related_experiences(self, todo) -> list[dict]:
        try:
            from arc.application.experience.service import ExperienceService
            exp_svc = ExperienceService(self.db)
            exps = await exp_svc.search_similar(
                f"{todo.title} {todo.description or ''}", limit=3
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

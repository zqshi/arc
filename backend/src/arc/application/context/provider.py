from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.repositories.project import ProjectRepository, VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    project_name: str = ""
    project_description: str = ""
    tech_stack: str = ""
    conventions: str = ""
    repo_url: str = ""
    version_name: str = ""
    version_goal: str = ""
    sibling_requirements: list[dict] = field(default_factory=list)

    @property
    def has_project(self) -> bool:
        return bool(self.project_name)

    def to_prompt_section(self) -> str:
        if not self.has_project:
            return ""
        parts = [f"## 项目信息\n- 项目名称: {self.project_name}"]
        if self.project_description:
            parts.append(f"- 项目描述: {self.project_description}")
        if self.tech_stack:
            parts.append(f"- 技术栈: {self.tech_stack}")
        if self.repo_url:
            parts.append(f"- 代码仓库: {self.repo_url}")
        if self.version_name:
            parts.append(f"\n## 当前版本\n- 版本: {self.version_name}")
            if self.version_goal:
                parts.append(f"- 版本目标: {self.version_goal}")
        if self.conventions:
            parts.append(f"\n## 项目规范\n{self.conventions}")
        return "\n".join(parts)

    def to_agent_section(self) -> str:
        if not self.has_project:
            return ""
        parts = [f"## 项目背景\n项目: {self.project_name}"]
        if self.tech_stack:
            parts.append(f"技术栈: {self.tech_stack}")
        if self.version_name:
            parts.append(f"当前版本: {self.version_name}")
            if self.version_goal:
                parts.append(f"版本目标: {self.version_goal}")
        if self.conventions:
            parts.append(f"\n## 项目规范（必须遵守）\n{self.conventions}")
        if self.repo_url:
            parts.append(f"\n代码仓库: {self.repo_url}")
        return "\n".join(parts)


class ProjectContextProvider:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.project_repo = ProjectRepository(db)
        self.version_repo = VersionRepository(db)

    async def get_context(self, todo_id: uuid.UUID) -> ProjectContext:
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return ProjectContext()

        project = await self.project_repo.get_by_id(todo.project_id)
        if not project:
            return ProjectContext()

        ctx = ProjectContext(
            project_name=project.name,
            project_description=project.description,
            tech_stack=project.tech_stack,
            conventions=project.conventions,
            repo_url=project.repo_url,
        )

        if todo.version_id:
            version = await self.version_repo.get_by_id(todo.version_id)
            if version:
                ctx.version_name = version.name
                ctx.version_goal = version.goal

        return ctx

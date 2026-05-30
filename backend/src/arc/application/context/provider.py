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
    local_path: str = ""
    codebase_summary: str = ""
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
        if self.local_path:
            parts.append(f"- 本地工作目录: {self.local_path}")
        if self.version_name:
            parts.append(f"\n## 当前版本\n- 版本: {self.version_name}")
            if self.version_goal:
                parts.append(f"- 版本目标: {self.version_goal}")
        if self.codebase_summary:
            parts.append(f"\n## 代码库概况\n{self.codebase_summary}")
        if self.conventions:
            parts.append(f"\n## 项目规范\n{self.conventions}")
        if self.sibling_requirements:
            parts.append(
                "\n## 同版本其他需求\n以下是同版本正在进行的其他需求，生成方案时注意避免冲突："
            )
            for req in self.sibling_requirements:
                parts.append(f"- {req['title']}（状态: {req['status']}）")
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
        if self.codebase_summary:
            parts.append(f"\n## 代码库概况\n{self.codebase_summary}")
        if self.sibling_requirements:
            parts.append("\n## 同版本其他需求\n以下是同版本正在进行的其他需求，注意避免冲突：")
            for req in self.sibling_requirements:
                parts.append(f"- {req['title']}（状态: {req['status']}）")
        if self.repo_url:
            parts.append(f"\n代码仓库: {self.repo_url}")
        if self.local_path:
            parts.append(f"工作目录: {self.local_path}")
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
            local_path=project.local_path,
            codebase_summary=project.codebase_summary,
        )

        if todo.version_id:
            version = await self.version_repo.get_by_id(todo.version_id)
            if version:
                ctx.version_name = version.name
                ctx.version_goal = version.goal

            siblings = await self.todo_repo.list_by_version(
                todo.version_id,
                exclude_id=todo.id,
            )
            ctx.sibling_requirements = [
                {"title": s.title, "status": s.status.value} for s in siblings
            ]

        return ctx

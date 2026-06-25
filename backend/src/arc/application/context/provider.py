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
    charter: str = ""
    repo_url: str = ""
    local_path: str = ""
    codebase_summary: str = ""
    version_name: str = ""
    version_goal: str = ""
    version_analysis_summary: str = ""
    sibling_requirements: list[dict] = field(default_factory=list)
    project_type: str = ""

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
        if self.project_type:
            parts.append(f"- 项目类型: {self.project_type}")
        if self.repo_url:
            parts.append(f"- 代码仓库: {self.repo_url}")
        if self.local_path:
            parts.append(f"- 本地工作目录: {self.local_path}")
        if self.version_name:
            parts.append(f"\n## 当前版本\n- 版本: {self.version_name}")
            if self.version_goal:
                parts.append(f"- 版本目标: {self.version_goal}")
            if self.version_analysis_summary:
                parts.append(
                    f"\n## 版本分析洞察（AI 生成）\n{self.version_analysis_summary}"
                )
        if self.codebase_summary:
            parts.append(f"\n## 代码库概况\n{self.codebase_summary}")
        if self.charter:
            parts.append(f"\n## 项目宪章 (系统生成·按项目类型)\n{self.charter}")
        if self.conventions:
            parts.append(f"\n## 项目规范\n{self.conventions}")
        if self.sibling_requirements:
            parts.append(
                "\n## 同版本其他需求\n以下是同版本正在进行的其他需求，生成方案时注意避免冲突："
            )
            for req in self.sibling_requirements:
                source_tag = "AI建议" if req.get("from_analysis") else "手动"
                parts.append(
                    f"- {req['title']}（状态: {req['status']}，来源: {source_tag}）"
                )
        return "\n".join(parts)

    def to_agent_section(self) -> str:
        if not self.has_project:
            return ""
        parts = [f"## 项目背景\n项目: {self.project_name}"]
        if self.tech_stack:
            parts.append(f"技术栈: {self.tech_stack}")
        if self.project_type:
            parts.append(f"项目类型: {self.project_type}")
        if self.version_name:
            parts.append(f"当前版本: {self.version_name}")
            if self.version_goal:
                parts.append(f"版本目标: {self.version_goal}")
        if self.version_analysis_summary:
            parts.append(
                f"\n## 版本分析洞察\n{self.version_analysis_summary}"
            )
        if self.charter:
            parts.append(f"\n## 项目宪章 (系统生成·必须遵守)\n{self.charter}")
        if self.conventions:
            parts.append(f"\n## 项目规范（必须遵守）\n{self.conventions}")
        if self.codebase_summary:
            parts.append(f"\n## 代码库概况\n{self.codebase_summary}")
        if self.sibling_requirements:
            parts.append("\n## 同版本其他需求\n以下是同版本正在进行的其他需求，注意避免冲突：")
            for req in self.sibling_requirements:
                source_tag = "AI建议" if req.get("from_analysis") else "手动"
                parts.append(
                    f"- {req['title']}（状态: {req['status']}，来源: {source_tag}）"
                )
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
            charter=project.charter.markdown if project.charter else "",
            repo_url=project.repo_url,
            local_path=project.local_path,
            codebase_summary=project.codebase_summary,
            project_type=project.project_type.value if project.project_type else "",
        )

        if todo.version_id:
            version = await self.version_repo.get_by_id(todo.version_id)
            if version:
                ctx.version_name = version.name
                ctx.version_goal = version.goal

            # 注入版本分析缓存（如果有）
            ctx.version_analysis_summary = await self._get_analysis_summary(
                todo.version_id
            )

            siblings = await self.todo_repo.list_by_version(
                todo.version_id,
                exclude_id=todo.id,
            )
            ctx.sibling_requirements = [
                {
                    "title": s.title,
                    "status": s.status.value,
                    "from_analysis": bool(s.source_session_id),
                }
                for s in siblings
            ]

        return ctx

    async def _get_analysis_summary(self, version_id: uuid.UUID) -> str:
        """从缓存中获取版本分析摘要，截取关键部分避免过长。"""
        try:
            from arc.application.planning.analysis_service import AnalysisService

            analysis_svc = AnalysisService(self.db)
            result = await analysis_svc.get_latest(version_id)
            if not result:
                return ""

            content, suggestions = result

            # 构建精简摘要：suggestions + 正文前 800 字符
            parts = []

            if suggestions:
                items = []
                for s in suggestions[:5]:
                    items.append(
                        f"- [{s.get('priority', '?')}] {s.get('action', '')}"
                    )
                parts.append("**行动建议**:\n" + "\n".join(items))

            # 截取分析正文（去掉末尾的 JSON 块）
            import re
            body = re.sub(
                r'```json\s*\{[^`]*"suggestions"[^`]*\}\s*```',
                "",
                content,
                flags=re.DOTALL,
            ).strip()
            if body:
                truncated = body[:800]
                if len(body) > 800:
                    truncated += "\n..."
                parts.append(truncated)

            return "\n\n".join(parts)
        except Exception:
            logger.debug("Failed to load version analysis for context", exc_info=True)
            return ""

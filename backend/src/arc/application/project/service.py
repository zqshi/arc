from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.entity import Version
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


def _next_version_name(existing_versions: list[Version], version_type: str) -> str:
    latest = (0, 0, 0)
    for v in existing_versions:
        m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", v.name)
        if m:
            parsed = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            if parsed > latest:
                latest = parsed

    major, minor, patch = latest
    if major == 0 and minor == 0 and patch == 0:
        if version_type == "major":
            return "v1.0"
        return "v0.1"

    if version_type == "major":
        return f"v{major + 1}.0"
    if version_type == "minor":
        return f"v{major}.{minor + 1}"
    return f"v{major}.{minor}.{patch + 1}"


class VersionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.version_repo = VersionRepository(db)
        self.todo_repo = TodoRepository(db)

    async def create_version(
        self,
        project_id: uuid.UUID,
        *,
        name: str | None = None,
        goal: str = "",
        version_type: str = "minor",
        parent_version_id: uuid.UUID | None = None,
    ) -> Version:
        next_order = await self.version_repo._next_order(project_id)

        if name and name.strip():
            resolved_name = name.strip()
        else:
            all_versions = await self.version_repo.list_by_project(project_id)
            resolved_name = _next_version_name(all_versions, version_type)

        version = Version(
            project_id=project_id,
            name=resolved_name,
            goal=goal,
            order=next_order,
            parent_version_id=parent_version_id,
        )
        return await self.version_repo.create(version)

    async def delete_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> None:
        version = await self._get_version(project_id, version_id)
        if version.status.value == "released":
            raise ValueError("已发布版本不可删除")
        stats = await self.version_repo.count_todos_by_status(version_id)
        if sum(stats.values()) > 0:
            raise ValueError("请先删除版本下的需求后再删除版本")
        await self.version_repo.delete(version_id)

    async def activate_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> Version:
        version = await self._get_version(project_id, version_id)

        stats = await self.version_repo.count_todos_by_status(version_id)
        total = sum(stats.values())
        if total == 0:
            raise ValueError("版本下没有需求，无法激活")

        version.activate()
        await self.version_repo.update(version)
        return version

    async def release_version(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> tuple[Version, Version | None]:
        version = await self._get_version(project_id, version_id)

        stats = await self.version_repo.count_todos_by_status(version_id)
        incomplete = stats.get("pending", 0) + stats.get("active", 0) + stats.get("error", 0)
        if incomplete > 0:
            raise ValueError(f"还有 {incomplete} 条未完成需求，无法发布")

        version.release()

        todos, _ = await self.todo_repo.list_all(version_id=version_id, limit=10000)
        done_todos = [t for t in todos if t.status.value == "done"]

        # AI 生成 changelog，失败时降级为简单列表
        changelog = await self._generate_changelog(version, done_todos)
        if changelog:
            version.set_changelog(changelog)

        # 自动生成原型快照（snapshot）
        await self._snapshot_prototype(project_id, version_id, version)

        await self.version_repo.update(version)

        carry_over_version = await self._carry_over_todos(version)
        return version, carry_over_version

    async def _snapshot_prototype(
        self, project_id: uuid.UUID, version_id: uuid.UUID, version: "Version"
    ) -> None:
        """版本发布时生成不可变的原型快照。"""
        import logging

        logger = logging.getLogger(__name__)
        try:
            from arc.application.artifact.prototype_bundle import PrototypeBundleService

            svc = PrototypeBundleService(self.db)
            url = await svc.publish_bundle(project_id, version_id, snapshot=True)
            if url:
                version.set_prototype_preview_url(url)
                logger.info("Prototype snapshot for version %s: %s", version_id, url)
        except Exception as exc:
            logger.warning("Failed to snapshot prototype for version %s: %s", version_id, exc)

    async def _generate_changelog(
        self, version: Version, done_todos: list
    ) -> str:
        """AI 生成版本 changelog，失败时降级为 bullet list。"""
        if not done_todos:
            return ""

        # 构建 fallback
        fallback = "\n".join(f"- {t.title}" for t in done_todos)

        # 构建 LLM prompt
        todo_details = []
        for t in done_todos:
            line = f"- {t.title}"
            if t.description:
                line += f"\n  描述: {t.description[:200]}"
            todo_details.append(line)

        prompt = (
            f"你是一个产品经理，正在为版本 {version.name} 生成变更日志。\n\n"
            f"版本目标: {version.goal or '未指定'}\n\n"
            f"本版本完成的需求:\n{''.join(todo_details)}\n\n"
            "请生成一段简洁的中文变更日志（changelog），要求:\n"
            "1. 按功能类别分组（如: 新功能、优化、修复）\n"
            "2. 每条用 `- ` 开头，一句话概括\n"
            "3. 整体不超过 500 字\n"
            "4. 不要输出标题（如「变更日志」），直接输出内容\n"
            "5. 用户能从中快速了解这个版本做了什么"
        )

        try:
            from arc.application.ai.resilience import create_resilient_adapter
            from arc.application.ai.llm_adapter import LLMMessage

            adapter = create_resilient_adapter()
            try:
                response = await adapter.chat([LLMMessage(role="user", content=prompt)])
                if response.content and len(response.content.strip()) > 10:
                    return response.content.strip()
            finally:
                await adapter.close()
        except Exception:
            logger.debug("AI changelog generation failed, using fallback", exc_info=True)

        return fallback

    async def _carry_over_todos(self, released_version: Version) -> Version | None:
        todos, _ = await self.todo_repo.list_all(version_id=released_version.id, limit=10000)
        pending_todos = [t for t in todos if t.status.value != "done"]

        if not pending_todos:
            return None

        target = await self.version_repo.get_latest_planning(released_version.project_id)
        if not target:
            target = Version(
                project_id=released_version.project_id,
                name=f"{released_version.name}-next",
                parent_version_id=released_version.id,
            )
            target = await self.version_repo.create(target)

        for todo in pending_todos:
            todo.version_id = target.id
            await self.todo_repo.update(todo)

        return target

    async def _get_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> Version:
        version = await self.version_repo.get_by_id(version_id)
        if not version or version.project_id != project_id:
            raise ValueError("版本不存在")
        return version

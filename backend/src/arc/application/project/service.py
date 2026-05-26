from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.entity import Version
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository


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
        changelog_lines = [f"- {t.title}" for t in todos if t.status.value == "done"]
        if changelog_lines:
            version.set_changelog("\n".join(changelog_lines))

        await self.version_repo.update(version)

        carry_over_version = await self._carry_over_todos(version)
        return version, carry_over_version

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

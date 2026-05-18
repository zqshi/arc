from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.entity import Version
from arc.infrastructure.models.todo import Todo as TodoModel
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository


class VersionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.version_repo = VersionRepository(db)
        self.todo_repo = TodoRepository(db)

    async def activate_version(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> Version:
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

        todos = await self.todo_repo.list_all(version_id=version_id)
        changelog_lines = [f"- {t.title}" for t in todos if t.status.value == "done"]
        if changelog_lines:
            version.set_changelog("\n".join(changelog_lines))

        await self.version_repo.update(version)

        carry_over_version = await self._carry_over_todos(version)
        return version, carry_over_version

    async def _carry_over_todos(self, released_version: Version) -> Version | None:
        todos = await self.todo_repo.list_all(version_id=released_version.id)
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

    async def _get_version(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> Version:
        version = await self.version_repo.get_by_id(version_id)
        if not version or version.project_id != project_id:
            raise ValueError("版本不存在")
        return version

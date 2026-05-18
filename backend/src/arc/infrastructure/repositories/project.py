from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.entity import Project, Version
from arc.domain.project.value_objects import ProjectStatus, VersionStatus
from arc.infrastructure.models.project import ProjectModel, VersionModel
from arc.infrastructure.models.todo import Todo as TodoModel


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, project: Project) -> Project:
        model = ProjectModel(
            id=project.id,
            name=project.name,
            description=project.description,
            tech_stack=project.tech_stack,
            repo_url=project.repo_url,
            conventions=project.conventions,
            status=project.status.value,
        )
        self.db.add(model)
        await self.db.flush()
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        result = await self.db.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def list_all(self, include_archived: bool = False) -> list[Project]:
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        if not include_archived:
            stmt = stmt.where(ProjectModel.status != "archived")
        result = await self.db.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, project: Project) -> None:
        result = await self.db.execute(
            select(ProjectModel).where(ProjectModel.id == project.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.name = project.name
        model.description = project.description
        model.tech_stack = project.tech_stack
        model.repo_url = project.repo_url
        model.conventions = project.conventions
        model.status = project.status.value
        await self.db.flush()

    async def delete(self, project_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            name=model.name,
            description=model.description or "",
            tech_stack=model.tech_stack or "",
            repo_url=model.repo_url or "",
            conventions=model.conventions or "",
            status=ProjectStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class VersionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, version: Version) -> Version:
        if version.order == 0:
            version.order = await self._next_order(version.project_id)

        exists = await self.db.execute(
            select(VersionModel.id).where(
                VersionModel.project_id == version.project_id,
                VersionModel.name == version.name,
            )
        )
        if exists.scalar_one_or_none():
            raise ValueError(f"版本名称 '{version.name}' 已存在")

        model = VersionModel(
            id=version.id,
            project_id=version.project_id,
            name=version.name,
            goal=version.goal,
            status=version.status.value,
            parent_version_id=version.parent_version_id,
            order=version.order,
            changelog=version.changelog or None,
        )
        self.db.add(model)
        await self.db.flush()
        return version

    async def _next_order(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(VersionModel.order), 0) + 1).where(
                VersionModel.project_id == project_id
            )
        )
        return result.scalar_one()

    async def get_by_id(self, version_id: uuid.UUID) -> Version | None:
        result = await self.db.execute(
            select(VersionModel).where(VersionModel.id == version_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def list_by_project(self, project_id: uuid.UUID) -> list[Version]:
        result = await self.db.execute(
            select(VersionModel)
            .where(VersionModel.project_id == project_id)
            .order_by(VersionModel.order.desc())
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, version: Version) -> None:
        result = await self.db.execute(
            select(VersionModel).where(VersionModel.id == version.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.name = version.name
        model.goal = version.goal
        model.status = version.status.value
        model.parent_version_id = version.parent_version_id
        model.order = version.order
        model.changelog = version.changelog or None
        await self.db.flush()

    async def get_latest_planning(self, project_id: uuid.UUID) -> Version | None:
        result = await self.db.execute(
            select(VersionModel)
            .where(
                VersionModel.project_id == project_id,
                VersionModel.status == "planning",
            )
            .order_by(VersionModel.order.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def count_todos_by_status(self, version_id: uuid.UUID) -> dict[str, int]:
        result = await self.db.execute(
            select(TodoModel.status, func.count())
            .where(TodoModel.version_id == version_id)
            .group_by(TodoModel.status)
        )
        return dict(result.all())

    async def count_by_project(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(VersionModel).where(
                VersionModel.project_id == project_id
            )
        )
        return result.scalar_one()

    async def delete(self, version_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(VersionModel).where(VersionModel.id == version_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: VersionModel) -> Version:
        return Version(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            goal=model.goal or "",
            status=VersionStatus(model.status),
            parent_version_id=model.parent_version_id,
            order=model.order or 0,
            changelog=model.changelog or "",
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

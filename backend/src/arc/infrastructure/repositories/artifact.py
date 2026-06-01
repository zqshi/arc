from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.infrastructure.models.artifact import ArtifactModel


class ArtifactRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, artifact: Artifact) -> Artifact:
        model = ArtifactModel(
            id=artifact.id,
            todo_id=artifact.todo_id,
            phase_id=artifact.phase_id,
            artifact_type=artifact.artifact_type.value,
            content=artifact.content,
            version=artifact.version,
            is_confirmed=artifact.is_confirmed,
            confirmed_at=artifact.confirmed_at,
            preview_url=artifact.preview_url,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, artifact_id: uuid.UUID) -> Artifact | None:
        result = await self.db.execute(select(ArtifactModel).where(ArtifactModel.id == artifact_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_phase_id(self, phase_id: uuid.UUID) -> Artifact | None:
        result = await self.db.execute(
            select(ArtifactModel).where(ArtifactModel.phase_id == phase_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_todo_and_type(
        self,
        todo_id: uuid.UUID,
        artifact_type: ArtifactType,
    ) -> Artifact | None:
        result = await self.db.execute(
            select(ArtifactModel).where(
                ArtifactModel.todo_id == todo_id,
                ArtifactModel.artifact_type == artifact_type.value,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def upsert_by_type(self, artifact: Artifact) -> Artifact:
        existing = await self.get_by_todo_and_type(artifact.todo_id, artifact.artifact_type)
        if existing:
            existing.update_content(artifact.content)
            return await self.update(existing)
        return await self.create(artifact)

    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[Artifact]:
        result = await self.db.execute(
            select(ArtifactModel)
            .where(ArtifactModel.todo_id == todo_id)
            .order_by(ArtifactModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_project_and_type(
        self, project_id: uuid.UUID, artifact_type: "ArtifactType",
    ) -> list[Artifact]:
        """查询项目下指定类型的所有 artifact（通过 todo.project_id 关联）。"""
        from arc.infrastructure.models.todo import Todo as TodoModel

        result = await self.db.execute(
            select(ArtifactModel)
            .join(TodoModel, TodoModel.id == ArtifactModel.todo_id)
            .where(TodoModel.project_id == project_id)
            .where(ArtifactModel.artifact_type == artifact_type.value)
            .order_by(ArtifactModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_todo_ids(
        self, todo_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[Artifact]]:
        if not todo_ids:
            return {}
        result = await self.db.execute(
            select(ArtifactModel)
            .where(ArtifactModel.todo_id.in_(todo_ids))
            .order_by(ArtifactModel.created_at)
        )
        grouped: dict[uuid.UUID, list[Artifact]] = {}
        for model in result.scalars().all():
            art = self._to_entity(model)
            grouped.setdefault(art.todo_id, []).append(art)
        return grouped

    async def list_confirmed_by_todo(self, todo_id: uuid.UUID) -> list[Artifact]:
        result = await self.db.execute(
            select(ArtifactModel)
            .where(ArtifactModel.todo_id == todo_id, ArtifactModel.is_confirmed.is_(True))
            .order_by(ArtifactModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def update(self, artifact: Artifact) -> Artifact:
        result = await self.db.execute(select(ArtifactModel).where(ArtifactModel.id == artifact.id))
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Artifact {artifact.id} not found")
        model.content = artifact.content
        model.version = artifact.version
        model.is_confirmed = artifact.is_confirmed
        model.confirmed_at = artifact.confirmed_at
        model.preview_url = artifact.preview_url
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def delete_by_phase_id(self, phase_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(ArtifactModel).where(ArtifactModel.phase_id == phase_id)
        )
        for model in result.scalars().all():
            await self.db.delete(model)
        await self.db.flush()

    @staticmethod
    def _to_entity(model: ArtifactModel) -> Artifact:
        return Artifact(
            id=model.id,
            todo_id=model.todo_id,
            phase_id=model.phase_id,
            artifact_type=ArtifactType(model.artifact_type),
            content=model.content,
            version=model.version,
            is_confirmed=model.is_confirmed,
            confirmed_at=model.confirmed_at,
            preview_url=model.preview_url,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

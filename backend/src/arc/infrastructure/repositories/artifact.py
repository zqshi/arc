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
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, artifact_id: uuid.UUID) -> Artifact | None:
        result = await self.db.execute(
            select(ArtifactModel).where(ArtifactModel.id == artifact_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_phase_id(self, phase_id: uuid.UUID) -> Artifact | None:
        result = await self.db.execute(
            select(ArtifactModel).where(ArtifactModel.phase_id == phase_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_todo_and_type(
        self, todo_id: uuid.UUID, artifact_type: ArtifactType,
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

    async def list_confirmed_by_todo(self, todo_id: uuid.UUID) -> list[Artifact]:
        result = await self.db.execute(
            select(ArtifactModel)
            .where(ArtifactModel.todo_id == todo_id, ArtifactModel.is_confirmed == True)
            .order_by(ArtifactModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def update(self, artifact: Artifact) -> Artifact:
        result = await self.db.execute(
            select(ArtifactModel).where(ArtifactModel.id == artifact.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Artifact {artifact.id} not found")
        model.content = artifact.content
        model.version = artifact.version
        model.is_confirmed = artifact.is_confirmed
        model.confirmed_at = artifact.confirmed_at
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
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

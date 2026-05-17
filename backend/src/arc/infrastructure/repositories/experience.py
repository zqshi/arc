from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.experience.entity import Experience as ExpEntity
from arc.domain.experience.repository import IExperienceRepository
from arc.domain.todo.value_objects import ExperienceScope, Tag
from arc.infrastructure.models.experience import Experience as ExpModel


class ExperienceRepository(IExperienceRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, exp_id: uuid.UUID) -> ExpEntity | None:
        result = await self.db.execute(select(ExpModel).where(ExpModel.id == exp_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_all(self) -> list[ExpEntity]:
        result = await self.db.execute(
            select(ExpModel).order_by(ExpModel.created_at.desc())
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def search_by_embedding(
        self, embedding: list[float], limit: int = 10
    ) -> list[ExpEntity]:

        result = await self.db.execute(
            select(ExpModel)
            .where(ExpModel.embedding.isnot(None))
            .order_by(ExpModel.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_recently_reused(self, limit: int = 10) -> list[ExpEntity]:
        """Get experiences that have been reused, ordered by most recent update."""
        result = await self.db.execute(
            select(ExpModel)
            .where(ExpModel.reuse_count > 0)
            .order_by(ExpModel.updated_at.desc())
            .limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_scope(
        self, scope: ExperienceScope, limit: int = 50
    ) -> list[ExpEntity]:
        result = await self.db.execute(
            select(ExpModel)
            .where(ExpModel.scope == scope.value)
            .order_by(ExpModel.confidence.desc())
            .limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def create(self, entity: ExpEntity) -> ExpEntity:
        model = ExpModel(
            id=entity.id,
            todo_id=entity.todo_id,
            title=entity.title,
            scope=entity.scope.value,
            problem=entity.problem,
            solution=entity.solution,
            decisions=entity.decisions or None,
            pitfalls=entity.pitfalls or None,
            applicable_scenarios=entity.applicable_scenarios,
            tags=[{"label": t.label, "color": t.color} for t in entity.tags],
            embedding=entity.embedding,
            confidence=entity.confidence,
            reuse_count=entity.reuse_count,
            metadata_=entity.metadata or None,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: ExpEntity) -> ExpEntity:
        result = await self.db.execute(select(ExpModel).where(ExpModel.id == entity.id))
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Experience {entity.id} not found")
        model.title = entity.title
        model.scope = entity.scope.value
        model.problem = entity.problem
        model.solution = entity.solution
        model.decisions = entity.decisions or None
        model.pitfalls = entity.pitfalls or None
        model.applicable_scenarios = entity.applicable_scenarios
        model.tags = [{"label": t.label, "color": t.color} for t in entity.tags]
        model.confidence = entity.confidence
        model.reuse_count = entity.reuse_count
        model.metadata_ = entity.metadata or None
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: ExpModel) -> ExpEntity:
        tags = []
        if model.tags:
            tags = [Tag(label=t["label"], color=t["color"]) for t in model.tags]
        return ExpEntity(
            id=model.id,
            todo_id=model.todo_id,
            title=model.title,
            scope=ExperienceScope(model.scope) if model.scope else ExperienceScope.TODO,
            problem=model.problem,
            solution=model.solution,
            decisions=model.decisions or [],
            pitfalls=model.pitfalls or [],
            applicable_scenarios=model.applicable_scenarios,
            tags=tags,
            embedding=list(model.embedding) if model.embedding else None,
            confidence=model.confidence,
            reuse_count=model.reuse_count,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

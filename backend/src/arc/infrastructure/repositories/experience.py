from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.experience.entity import Experience as ExpEntity
from arc.domain.experience.repository import IExperienceRepository
from arc.domain.todo.value_objects import ExperienceScope, ExperienceStatus, Tag
from arc.infrastructure.models.experience import (
    Experience as ExpModel,
    ExperienceFeedback as FeedbackModel,
)


class ExperienceRepository(IExperienceRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, exp_id: uuid.UUID) -> ExpEntity | None:
        result = await self.db.execute(select(ExpModel).where(ExpModel.id == exp_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_all(
        self,
        project_id: uuid.UUID | None = None,
        status: ExperienceStatus | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[ExpEntity]:
        stmt = select(ExpModel).where(ExpModel.status != "archived").order_by(ExpModel.created_at.desc())
        if user_id:
            stmt = stmt.where(ExpModel.user_id == user_id)
        if project_id:
            stmt = stmt.where(
                (ExpModel.project_id == project_id)
                | (ExpModel.scope == "personal")
            )
        if status:
            stmt = stmt.where(ExpModel.status == status.value)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def search_by_embedding(
        self, embedding: list[float], limit: int = 10, project_id: uuid.UUID | None = None,
    ) -> list[ExpEntity]:
        stmt = (
            select(ExpModel)
            .where(ExpModel.embedding.isnot(None))
            .where(ExpModel.status == "confirmed")
        )
        if project_id:
            stmt = stmt.where(
                (ExpModel.project_id == project_id)
                | (ExpModel.scope == "personal")
            )
        stmt = stmt.order_by(ExpModel.embedding.cosine_distance(embedding)).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_recently_reused(self, limit: int = 10) -> list[ExpEntity]:
        result = await self.db.execute(
            select(ExpModel)
            .where(ExpModel.reuse_count > 0)
            .order_by(ExpModel.updated_at.desc())
            .limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_scope(
        self, scope: ExperienceScope, limit: int = 50, project_id: uuid.UUID | None = None,
    ) -> list[ExpEntity]:
        stmt = (
            select(ExpModel)
            .where(ExpModel.scope == scope.value)
            .where(ExpModel.status == "confirmed")
        )
        if project_id and scope == ExperienceScope.PROJECT:
            stmt = stmt.where(ExpModel.project_id == project_id)
        stmt = stmt.order_by(ExpModel.confidence.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_high_confidence(
        self, project_id: uuid.UUID, min_confidence: float = 0.8, min_reuse: int = 3,
    ) -> list[ExpEntity]:
        stmt = (
            select(ExpModel)
            .where(ExpModel.project_id == project_id)
            .where(ExpModel.status == "confirmed")
            .where(ExpModel.confidence >= min_confidence)
            .where(ExpModel.reuse_count >= min_reuse)
            .order_by(ExpModel.confidence.desc())
        )
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def has_feedback(self, experience_id: uuid.UUID, todo_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(FeedbackModel).where(
                FeedbackModel.experience_id == experience_id,
                FeedbackModel.todo_id == todo_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def add_feedback(
        self, experience_id: uuid.UUID, todo_id: uuid.UUID, helpful: bool,
    ) -> None:
        fb = FeedbackModel(
            experience_id=experience_id,
            todo_id=todo_id,
            helpful=helpful,
        )
        self.db.add(fb)
        await self.db.flush()

    async def create(self, entity: ExpEntity, user_id: uuid.UUID | None = None) -> ExpEntity:
        model = ExpModel(
            id=entity.id,
            user_id=user_id,
            todo_id=entity.todo_id,
            project_id=entity.project_id,
            title=entity.title,
            scope=entity.scope.value,
            status=entity.status.value,
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
        model.status = entity.status.value
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

        scope_val = model.scope
        if scope_val in ("personal", "project"):
            scope = ExperienceScope(scope_val)
        else:
            scope = ExperienceScope.PROJECT

        status_val = model.status if hasattr(model, "status") and model.status else "draft"
        if status_val in ("draft", "confirmed", "archived"):
            status = ExperienceStatus(status_val)
        else:
            status = ExperienceStatus.DRAFT

        return ExpEntity(
            id=model.id,
            todo_id=model.todo_id,
            project_id=model.project_id if hasattr(model, "project_id") else None,
            title=model.title,
            scope=scope,
            status=status,
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

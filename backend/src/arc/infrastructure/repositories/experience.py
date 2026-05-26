from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.experience.entity import Experience as ExpEntity
from arc.domain.experience.repository import IExperienceRepository
from arc.domain.todo.value_objects import (
    ExperienceCategory,
    ExperienceScope,
    ExperienceSource,
    ExperienceStatus,
    Tag,
)
from arc.infrastructure.models.experience import (
    Experience as ExpModel,
)
from arc.infrastructure.models.experience import (
    ExperienceFeedback as FeedbackModel,
)
from arc.infrastructure.models.user import ProjectMemberModel


class ExperienceRepository(IExperienceRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self, exp_id: uuid.UUID, *, user_id: uuid.UUID | None = None
    ) -> ExpEntity | None:
        stmt = select(ExpModel).where(ExpModel.id == exp_id)
        if user_id:
            stmt = stmt.where(ExpModel.user_id == user_id)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_all(
        self,
        project_id: uuid.UUID | None = None,
        status: ExperienceStatus | None = None,
        category: ExperienceCategory | None = None,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ExpEntity], int]:
        base = select(ExpModel).where(ExpModel.status != "archived")
        if user_id:
            user_project_ids = (
                select(ProjectMemberModel.project_id)
                .where(ProjectMemberModel.user_id == user_id)
                .scalar_subquery()
            )
            base = base.where(
                or_(
                    ExpModel.user_id == user_id,
                    ExpModel.project_id.in_(user_project_ids),
                )
            )
        if project_id:
            base = base.where(ExpModel.project_id == project_id)
        if status:
            base = base.where(ExpModel.status == status.value)
        if category:
            base = base.where(ExpModel.category == category.value)

        count_result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar() or 0

        stmt = base.order_by(ExpModel.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()], total

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        project_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[ExpEntity]:
        stmt = (
            select(ExpModel)
            .where(ExpModel.embedding.isnot(None))
            .where(ExpModel.status == "confirmed")
        )
        if user_id:
            user_project_ids = (
                select(ProjectMemberModel.project_id)
                .where(ProjectMemberModel.user_id == user_id)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    ExpModel.user_id == user_id,
                    ExpModel.project_id.in_(user_project_ids),
                )
            )
        if project_id:
            stmt = stmt.where(ExpModel.project_id == project_id)
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
        self,
        scope: ExperienceScope,
        limit: int = 50,
        project_id: uuid.UUID | None = None,
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
        self,
        project_id: uuid.UUID,
        min_confidence: float = 0.8,
        min_reuse: int = 3,
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
        self,
        experience_id: uuid.UUID,
        todo_id: uuid.UUID,
        helpful: bool,
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
            version_id=entity.version_id,
            source_experience_id=entity.source_experience_id,
            title=entity.title,
            scope=entity.scope.value,
            status=entity.status.value,
            category=entity.category.value,
            source=entity.source.value,
            problem=entity.problem,
            solution=entity.solution,
            decisions=entity.decisions or None,
            pitfalls=entity.pitfalls or None,
            applicable_scenarios=entity.applicable_scenarios,
            tags=[{"label": t.label, "color": t.color} for t in entity.tags],
            embedding=entity.embedding,
            confidence=entity.confidence,
            reuse_count=entity.reuse_count,
            half_life_days=entity.half_life_days,
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
        model.category = entity.category.value
        model.source = entity.source.value
        model.version_id = entity.version_id
        model.source_experience_id = entity.source_experience_id
        model.problem = entity.problem
        model.solution = entity.solution
        model.decisions = entity.decisions or None
        model.pitfalls = entity.pitfalls or None
        model.applicable_scenarios = entity.applicable_scenarios
        model.tags = [{"label": t.label, "color": t.color} for t in entity.tags]
        model.confidence = entity.confidence
        model.reuse_count = entity.reuse_count
        model.half_life_days = entity.half_life_days
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

        cat_val = getattr(model, "category", None) or "technical"
        try:
            category = ExperienceCategory(cat_val)
        except ValueError:
            category = ExperienceCategory.TECHNICAL

        src_val = getattr(model, "source", None) or "manual"
        try:
            source = ExperienceSource(src_val)
        except ValueError:
            source = ExperienceSource.MANUAL

        return ExpEntity(
            id=model.id,
            todo_id=model.todo_id,
            project_id=model.project_id if hasattr(model, "project_id") else None,
            version_id=getattr(model, "version_id", None),
            source_experience_id=getattr(model, "source_experience_id", None),
            title=model.title,
            scope=scope,
            status=status,
            category=category,
            source=source,
            problem=model.problem,
            solution=model.solution,
            decisions=model.decisions or [],
            pitfalls=model.pitfalls or [],
            applicable_scenarios=model.applicable_scenarios,
            tags=tags,
            embedding=list(model.embedding) if model.embedding is not None else None,
            confidence=model.confidence,
            reuse_count=model.reuse_count,
            half_life_days=getattr(model, "half_life_days", 180),
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_for_decay(self, batch_size: int = 500) -> list[ExpEntity]:
        stmt = (
            select(ExpModel)
            .where(ExpModel.status.in_(["draft", "confirmed"]))
            .where(ExpModel.confidence > 0)
            .limit(batch_size)
        )
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def batch_update_confidence(self, updates: list[tuple[uuid.UUID, float]]) -> int:
        from sqlalchemy import update

        count = 0
        for exp_id, new_conf in updates:
            result = await self.db.execute(
                update(ExpModel).where(ExpModel.id == exp_id).values(confidence=new_conf)
            )
            count += result.rowcount
        await self.db.flush()
        return count

    async def get_reuse_analytics(self, project_id: uuid.UUID | None = None) -> dict:
        base = select(ExpModel).where(ExpModel.status.in_(["draft", "confirmed"]))
        if project_id:
            base = base.where((ExpModel.project_id == project_id) | (ExpModel.scope == "personal"))

        cat_stmt = select(
            ExpModel.category,
            func.count().label("count"),
            func.sum(ExpModel.reuse_count).label("total_reuse"),
        ).where(ExpModel.status.in_(["draft", "confirmed"]))
        if project_id:
            cat_stmt = cat_stmt.where(
                (ExpModel.project_id == project_id) | (ExpModel.scope == "personal")
            )
        cat_stmt = cat_stmt.group_by(ExpModel.category)
        cat_result = await self.db.execute(cat_stmt)
        by_category = [
            {"category": r.category, "count": r.count, "total_reuse": r.total_reuse or 0}
            for r in cat_result.all()
        ]

        top_stmt = (
            select(ExpModel)
            .where(ExpModel.reuse_count > 0)
            .where(ExpModel.status.in_(["draft", "confirmed"]))
        )
        if project_id:
            top_stmt = top_stmt.where(
                (ExpModel.project_id == project_id) | (ExpModel.scope == "personal")
            )
        top_stmt = top_stmt.order_by(ExpModel.reuse_count.desc()).limit(10)
        top_result = await self.db.execute(top_stmt)
        top_reused = [self._to_entity(r) for r in top_result.scalars().all()]

        stale_stmt = (
            select(func.count())
            .select_from(ExpModel)
            .where(ExpModel.status.in_(["draft", "confirmed"]))
            .where(ExpModel.confidence < 0.3)
        )
        if project_id:
            stale_stmt = stale_stmt.where(
                (ExpModel.project_id == project_id) | (ExpModel.scope == "personal")
            )
        stale_result = await self.db.execute(stale_stmt)
        stale_count = stale_result.scalar() or 0

        return {
            "by_category": by_category,
            "top_reused": top_reused,
            "stale_count": stale_count,
        }

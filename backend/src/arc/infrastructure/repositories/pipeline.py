from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.pipeline.entity import PipelinePhase
from arc.domain.pipeline.value_objects import PhaseStatus, PhaseType
from arc.infrastructure.models.pipeline import PipelinePhaseModel


class PipelinePhaseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, phase: PipelinePhase) -> PipelinePhase:
        model = PipelinePhaseModel(
            id=phase.id,
            todo_id=phase.todo_id,
            phase_type=phase.phase_type.value,
            status=phase.status.value,
            conversation_id=phase.conversation_id,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def create_batch(self, phases: list[PipelinePhase]) -> list[PipelinePhase]:
        models = []
        for phase in phases:
            model = PipelinePhaseModel(
                id=phase.id,
                todo_id=phase.todo_id,
                phase_type=phase.phase_type.value,
                status=phase.status.value,
                conversation_id=phase.conversation_id,
            )
            self.db.add(model)
            models.append(model)
        await self.db.flush()
        for m in models:
            await self.db.refresh(m)
        return [self._to_entity(m) for m in models]

    async def get_by_id(self, phase_id: uuid.UUID) -> PipelinePhase | None:
        result = await self.db.execute(
            select(PipelinePhaseModel).where(PipelinePhaseModel.id == phase_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_todo_and_type(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> PipelinePhase | None:
        result = await self.db.execute(
            select(PipelinePhaseModel).where(
                PipelinePhaseModel.todo_id == todo_id,
                PipelinePhaseModel.phase_type == phase_type.value,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[PipelinePhase]:
        result = await self.db.execute(
            select(PipelinePhaseModel)
            .where(PipelinePhaseModel.todo_id == todo_id)
            .order_by(PipelinePhaseModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def update(self, phase: PipelinePhase) -> PipelinePhase:
        result = await self.db.execute(
            select(PipelinePhaseModel).where(PipelinePhaseModel.id == phase.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"PipelinePhase {phase.id} not found")
        model.status = phase.status.value
        model.conversation_id = phase.conversation_id
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def delete_by_todo_id(self, todo_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(PipelinePhaseModel).where(PipelinePhaseModel.todo_id == todo_id)
        )
        for model in result.scalars().all():
            await self.db.delete(model)
        await self.db.flush()

    @staticmethod
    def _to_entity(model: PipelinePhaseModel) -> PipelinePhase:
        return PipelinePhase(
            id=model.id,
            todo_id=model.todo_id,
            phase_type=PhaseType(model.phase_type),
            status=PhaseStatus(model.status),
            conversation_id=model.conversation_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

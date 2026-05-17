from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.pipeline.entity import PipelinePhase
from arc.domain.pipeline.value_objects import PhaseType


class PipelinePhaseRepository(ABC):
    @abstractmethod
    async def create(self, phase: PipelinePhase) -> PipelinePhase: ...

    @abstractmethod
    async def create_batch(self, phases: list[PipelinePhase]) -> list[PipelinePhase]: ...

    @abstractmethod
    async def get_by_id(self, phase_id: uuid.UUID) -> PipelinePhase | None: ...

    @abstractmethod
    async def get_by_todo_and_type(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> PipelinePhase | None: ...

    @abstractmethod
    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[PipelinePhase]: ...

    @abstractmethod
    async def update(self, phase: PipelinePhase) -> PipelinePhase: ...

    @abstractmethod
    async def delete_by_todo_id(self, todo_id: uuid.UUID) -> None: ...

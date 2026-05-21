from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.experience.entity import Experience
from arc.domain.todo.value_objects import ExperienceScope, ExperienceStatus


class IExperienceRepository(ABC):
    @abstractmethod
    async def get_by_id(self, experience_id: uuid.UUID) -> Experience | None: ...

    @abstractmethod
    async def list_all(
        self, project_id: uuid.UUID | None = None, status: ExperienceStatus | None = None,
    ) -> list[Experience]: ...

    @abstractmethod
    async def list_by_scope(
        self, scope: ExperienceScope, limit: int = 50, project_id: uuid.UUID | None = None,
    ) -> list[Experience]: ...

    @abstractmethod
    async def search_by_embedding(
        self, embedding: list[float], limit: int = 10,
        project_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> list[Experience]: ...

    @abstractmethod
    async def create(self, experience: Experience) -> Experience: ...

    @abstractmethod
    async def update(self, experience: Experience) -> Experience: ...

    @abstractmethod
    async def has_feedback(self, experience_id: uuid.UUID, todo_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def add_feedback(
        self, experience_id: uuid.UUID, todo_id: uuid.UUID, helpful: bool,
    ) -> None: ...

    @abstractmethod
    async def list_high_confidence(
        self, project_id: uuid.UUID, min_confidence: float = 0.8, min_reuse: int = 3,
    ) -> list[Experience]: ...

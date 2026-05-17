from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.experience.entity import Experience
from arc.domain.todo.value_objects import ExperienceScope


class IExperienceRepository(ABC):
    @abstractmethod
    async def get_by_id(self, experience_id: uuid.UUID) -> Experience | None: ...

    @abstractmethod
    async def list_all(self) -> list[Experience]: ...

    @abstractmethod
    async def list_by_scope(
        self, scope: ExperienceScope, limit: int = 50
    ) -> list[Experience]: ...

    @abstractmethod
    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
    ) -> list[Experience]: ...

    @abstractmethod
    async def create(self, experience: Experience) -> Experience: ...

    @abstractmethod
    async def update(self, experience: Experience) -> Experience: ...

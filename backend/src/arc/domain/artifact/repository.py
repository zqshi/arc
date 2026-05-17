from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.artifact.entity import Artifact


class ArtifactRepository(ABC):
    @abstractmethod
    async def create(self, artifact: Artifact) -> Artifact: ...

    @abstractmethod
    async def get_by_id(self, artifact_id: uuid.UUID) -> Artifact | None: ...

    @abstractmethod
    async def get_by_phase_id(self, phase_id: uuid.UUID) -> Artifact | None: ...

    @abstractmethod
    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[Artifact]: ...

    @abstractmethod
    async def list_confirmed_by_todo(self, todo_id: uuid.UUID) -> list[Artifact]: ...

    @abstractmethod
    async def update(self, artifact: Artifact) -> Artifact: ...

    @abstractmethod
    async def delete_by_phase_id(self, phase_id: uuid.UUID) -> None: ...

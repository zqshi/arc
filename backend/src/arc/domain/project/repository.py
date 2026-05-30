from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.project.entity import Project, Version


class AbstractProjectRepository(ABC):
    """Domain-level contract for project persistence."""

    @abstractmethod
    async def create(
        self,
        project: Project,
        user_id: uuid.UUID | None = None,
    ) -> Project: ...

    @abstractmethod
    async def get_by_id(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> Project | None: ...

    @abstractmethod
    async def list_all(
        self,
        include_archived: bool = False,
        user_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> list[Project]: ...

    @abstractmethod
    async def update(self, project: Project) -> None: ...

    @abstractmethod
    async def delete(self, project_id: uuid.UUID) -> bool: ...


class AbstractVersionRepository(ABC):
    """Domain-level contract for version persistence."""

    @abstractmethod
    async def create(self, version: Version) -> Version: ...

    @abstractmethod
    async def get_by_id(self, version_id: uuid.UUID) -> Version | None: ...

    @abstractmethod
    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 200,
    ) -> list[Version]: ...

    @abstractmethod
    async def update(self, version: Version) -> None: ...

    @abstractmethod
    async def get_latest_planning(
        self, project_id: uuid.UUID
    ) -> Version | None: ...

    @abstractmethod
    async def count_todos_by_status(
        self, version_id: uuid.UUID
    ) -> dict[str, int]: ...

    @abstractmethod
    async def batch_count_todos_by_status(
        self,
        version_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, int]]: ...

    @abstractmethod
    async def count_by_project(self, project_id: uuid.UUID) -> int: ...

    @abstractmethod
    async def delete(self, version_id: uuid.UUID) -> bool: ...

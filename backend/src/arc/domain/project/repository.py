from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.project.entity import Project, Version


class ProjectRepository(ABC):
    @abstractmethod
    async def create(self, project: Project) -> Project: ...

    @abstractmethod
    async def get_by_id(self, project_id: uuid.UUID) -> Project | None: ...

    @abstractmethod
    async def list_all(self, include_archived: bool = False) -> list[Project]: ...

    @abstractmethod
    async def update(self, project: Project) -> None: ...


class VersionRepository(ABC):
    @abstractmethod
    async def create(self, version: Version) -> Version: ...

    @abstractmethod
    async def get_by_id(self, version_id: uuid.UUID) -> Version | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: uuid.UUID) -> list[Version]: ...

    @abstractmethod
    async def update(self, version: Version) -> None: ...

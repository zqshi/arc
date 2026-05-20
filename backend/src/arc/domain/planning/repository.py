from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.planning.entity import DeliverableTracker, Document, PlanningSession


class DocumentRepository(ABC):
    @abstractmethod
    async def create(self, doc: Document) -> Document: ...

    @abstractmethod
    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: uuid.UUID) -> list[Document]: ...

    @abstractmethod
    async def update(self, doc: Document) -> None: ...

    @abstractmethod
    async def delete(self, doc_id: uuid.UUID) -> bool: ...


class PlanningSessionRepository(ABC):
    @abstractmethod
    async def create(self, session: PlanningSession) -> PlanningSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: uuid.UUID) -> PlanningSession | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: uuid.UUID) -> list[PlanningSession]: ...

    @abstractmethod
    async def update(self, session: PlanningSession) -> None: ...


class DeliverableTrackerRepository(ABC):
    @abstractmethod
    async def create(self, tracker: DeliverableTracker) -> DeliverableTracker: ...

    @abstractmethod
    async def get_by_todo_id(self, todo_id: uuid.UUID) -> DeliverableTracker | None: ...

    @abstractmethod
    async def update(self, tracker: DeliverableTracker) -> None: ...

    @abstractmethod
    async def upsert(self, tracker: DeliverableTracker) -> DeliverableTracker: ...

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus


class AbstractTodoRepository(ABC):
    """Domain-level contract for todo persistence."""

    @abstractmethod
    async def get_by_id(
        self,
        todo_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> Todo | None: ...

    @abstractmethod
    async def list_all(
        self,
        project_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Todo], int]: ...

    @abstractmethod
    async def list_by_status(
        self,
        status: TodoStatus,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Todo], int]: ...

    @abstractmethod
    async def create(
        self,
        entity: Todo,
        user_id: uuid.UUID | None = None,
    ) -> Todo: ...

    @abstractmethod
    async def update(self, entity: Todo) -> Todo: ...

    @abstractmethod
    async def delete(
        self,
        todo_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> None: ...

    @abstractmethod
    async def mark_seen(self, todo_id: uuid.UUID) -> None: ...

    @abstractmethod
    async def list_by_session(
        self, session_id: uuid.UUID
    ) -> list[Todo]: ...

    @abstractmethod
    async def list_by_version(
        self,
        version_id: uuid.UUID,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> list[Todo]: ...

    @abstractmethod
    async def find_by_github_issue(
        self, project_id: uuid.UUID, issue_number: int
    ) -> Todo | None: ...


# Backward-compatible alias
ITodoRepository = AbstractTodoRepository

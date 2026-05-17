from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus


class ITodoRepository(ABC):
    @abstractmethod
    async def get_by_id(self, todo_id: uuid.UUID) -> Todo | None: ...

    @abstractmethod
    async def list_all(self) -> list[Todo]: ...

    @abstractmethod
    async def list_by_status(self, status: TodoStatus) -> list[Todo]: ...

    @abstractmethod
    async def create(self, todo: Todo) -> Todo: ...

    @abstractmethod
    async def update(self, todo: Todo) -> Todo: ...

    @abstractmethod
    async def delete(self, todo_id: uuid.UUID) -> None: ...

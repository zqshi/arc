from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.entity import Todo as TodoEntity
from arc.domain.todo.value_objects import Tag, TodoStatus
from arc.infrastructure.models.todo import Todo as TodoModel


class TodoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, todo_id: uuid.UUID) -> TodoEntity | None:
        result = await self.db.execute(select(TodoModel).where(TodoModel.id == todo_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_all(self) -> list[TodoEntity]:
        result = await self.db.execute(
            select(TodoModel).order_by(TodoModel.created_at.desc())
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_status(self, status: TodoStatus) -> list[TodoEntity]:
        result = await self.db.execute(
            select(TodoModel)
            .where(TodoModel.status == status.value)
            .order_by(TodoModel.created_at.desc())
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def create(self, entity: TodoEntity) -> TodoEntity:
        model = TodoModel(
            id=entity.id,
            title=entity.title,
            description=entity.description,
            status=entity.status.value,
            current_phase=entity.current_phase.value if entity.current_phase else None,
            tags=[{"label": t.label, "color": t.color} for t in entity.tags],
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: TodoEntity) -> TodoEntity:
        result = await self.db.execute(select(TodoModel).where(TodoModel.id == entity.id))
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Todo {entity.id} not found")
        model.title = entity.title
        model.description = entity.description
        model.status = entity.status.value
        model.current_phase = entity.current_phase.value if entity.current_phase else None
        model.tags = [{"label": t.label, "color": t.color} for t in entity.tags]
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def delete(self, todo_id: uuid.UUID) -> None:
        result = await self.db.execute(select(TodoModel).where(TodoModel.id == todo_id))
        model = result.scalar_one_or_none()
        if model:
            await self.db.delete(model)
            await self.db.flush()

    @staticmethod
    def _to_entity(model: TodoModel) -> TodoEntity:
        tags = []
        if model.tags:
            tags = [Tag(label=t["label"], color=t["color"]) for t in model.tags]
        return TodoEntity(
            id=model.id,
            title=model.title,
            description=model.description or "",
            status=TodoStatus(model.status),
            current_phase=PhaseType(model.current_phase) if model.current_phase else None,
            tags=tags,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

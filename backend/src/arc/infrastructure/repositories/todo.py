from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.entity import Todo as TodoEntity
from arc.domain.todo.repository import AbstractTodoRepository
from arc.domain.todo.value_objects import Tag, TodoStatus
from arc.infrastructure.models.todo import Todo as TodoModel
from arc.infrastructure.models.todo import TodoDependency


class TodoDependencyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, todo_id: uuid.UUID, depends_on_id: uuid.UUID) -> None:
        dep = TodoDependency(todo_id=todo_id, depends_on_id=depends_on_id)
        self.db.add(dep)
        await self.db.flush()

    async def remove(self, todo_id: uuid.UUID, depends_on_id: uuid.UUID) -> bool:
        stmt = select(TodoDependency).where(
            TodoDependency.todo_id == todo_id,
            TodoDependency.depends_on_id == depends_on_id,
        )
        result = await self.db.execute(stmt)
        dep = result.scalar_one_or_none()
        if dep:
            await self.db.delete(dep)
            await self.db.flush()
            return True
        return False

    async def get_blocked_by(self, todo_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(TodoDependency.depends_on_id).where(TodoDependency.todo_id == todo_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_blocks(self, todo_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = select(TodoDependency.todo_id).where(TodoDependency.depends_on_id == todo_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_map(self, todo_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
        if not todo_ids:
            return {}
        stmt = select(TodoDependency).where(TodoDependency.todo_id.in_(todo_ids))
        result = await self.db.execute(stmt)
        dep_map: dict[uuid.UUID, list[uuid.UUID]] = {tid: [] for tid in todo_ids}
        for dep in result.scalars().all():
            dep_map[dep.todo_id].append(dep.depends_on_id)
        return dep_map

    async def get_blocks_map(self, todo_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
        if not todo_ids:
            return {}
        stmt = select(TodoDependency).where(TodoDependency.depends_on_id.in_(todo_ids))
        result = await self.db.execute(stmt)
        blocks_map: dict[uuid.UUID, list[uuid.UUID]] = {tid: [] for tid in todo_ids}
        for dep in result.scalars().all():
            blocks_map[dep.depends_on_id].append(dep.todo_id)
        return blocks_map


class TodoRepository(AbstractTodoRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(
        self,
        todo_id: uuid.UUID,
        *,
        user_id: uuid.UUID | None = None,
    ) -> TodoEntity | None:
        stmt = select(TodoModel).where(TodoModel.id == todo_id)
        if user_id:
            stmt = stmt.where(TodoModel.user_id == user_id)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_all(
        self,
        project_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[TodoEntity], int]:
        base = select(TodoModel)
        if user_id:
            base = base.where(TodoModel.user_id == user_id)
        if project_id:
            base = base.where(TodoModel.project_id == project_id)
        if version_id:
            base = base.where(TodoModel.version_id == version_id)

        count_result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar() or 0

        stmt = base.order_by(TodoModel.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()], total

    async def list_by_status(
        self,
        status: TodoStatus,
        user_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[TodoEntity], int]:
        base = select(TodoModel).where(TodoModel.status == status.value)
        if user_id:
            base = base.where(TodoModel.user_id == user_id)

        count_result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar() or 0

        stmt = base.order_by(TodoModel.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()], total

    async def create(self, entity: TodoEntity, user_id: uuid.UUID | None = None) -> TodoEntity:
        model = TodoModel(
            id=entity.id,
            user_id=user_id,
            title=entity.title,
            description=entity.description,
            status=entity.status.value,
            project_id=entity.project_id,
            version_id=entity.version_id,
            priority=entity.priority,
            current_phase=entity.current_phase.value if entity.current_phase else None,
            tags=[{"label": t.label, "color": t.color} for t in entity.tags],
            source_session_id=entity.source_session_id,
            source_feature_key=entity.source_feature_key or None,
            github_issue_number=entity.github_issue_number,
            github_pr_url=entity.github_pr_url or None,
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
        model.project_id = entity.project_id
        model.version_id = entity.version_id
        model.priority = entity.priority
        model.current_phase = entity.current_phase.value if entity.current_phase else None
        model.tags = [{"label": t.label, "color": t.color} for t in entity.tags]
        model.source_session_id = entity.source_session_id
        model.source_feature_key = entity.source_feature_key or None
        model.github_issue_number = entity.github_issue_number
        model.github_pr_url = entity.github_pr_url or None
        model.error_reason = entity.error_reason or None
        model.suspended_reason = entity.suspended_reason or None
        model.suspended_model_version = entity.suspended_model_version
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def mark_seen(self, todo_id: uuid.UUID) -> None:
        from sqlalchemy import update

        await self.db.execute(
            update(TodoModel)
            .where(TodoModel.id == todo_id)
            .values(last_seen_at=func.now(), updated_at=TodoModel.updated_at)
            .execution_options(synchronize_session=False)
        )
        await self.db.flush()

    async def delete(self, todo_id: uuid.UUID, *, user_id: uuid.UUID | None = None) -> None:
        stmt = select(TodoModel).where(TodoModel.id == todo_id)
        if user_id:
            stmt = stmt.where(TodoModel.user_id == user_id)
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self.db.delete(model)
            await self.db.flush()

    async def list_by_session(self, session_id: uuid.UUID) -> list[TodoEntity]:
        stmt = (
            select(TodoModel)
            .where(TodoModel.source_session_id == session_id)
            .order_by(TodoModel.created_at)
        )
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_by_version(
        self,
        version_id: uuid.UUID,
        *,
        exclude_id: uuid.UUID | None = None,
    ) -> list[TodoEntity]:
        stmt = select(TodoModel).where(TodoModel.version_id == version_id)
        if exclude_id:
            stmt = stmt.where(TodoModel.id != exclude_id)
        stmt = stmt.order_by(TodoModel.created_at)
        result = await self.db.execute(stmt)
        return [self._to_entity(r) for r in result.scalars().all()]

    async def find_by_github_issue(
        self, project_id: uuid.UUID, issue_number: int
    ) -> TodoEntity | None:
        stmt = select(TodoModel).where(
            TodoModel.project_id == project_id,
            TodoModel.github_issue_number == issue_number,
        )
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    @staticmethod
    def _to_entity(model: TodoModel) -> TodoEntity:
        tags = []
        if model.tags:
            tags = [Tag(label=t["label"], color=t["color"]) for t in model.tags]
        return TodoEntity(
            id=model.id,
            title=model.title,
            description=model.description or "",
            project_id=model.project_id,
            version_id=model.version_id,
            status=TodoStatus(model.status),
            priority=model.priority if model.priority is not None else 2,
            current_phase=PhaseType(model.current_phase) if model.current_phase else None,
            tags=tags,
            source_session_id=model.source_session_id,
            source_feature_key=model.source_feature_key or "",
            github_issue_number=model.github_issue_number,
            github_pr_url=model.github_pr_url or "",
            error_reason=model.error_reason or "",
            suspended_reason=model.suspended_reason or "",
            suspended_model_version=model.suspended_model_version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_seen_at=model.last_seen_at,
        )

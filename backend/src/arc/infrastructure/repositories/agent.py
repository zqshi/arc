from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.agent.entity import AgentSession
from arc.domain.agent.repository import AgentSessionRepository as AgentSessionRepositoryABC
from arc.domain.agent.value_objects import AgentType, SessionStatus
from arc.infrastructure.models.agent import AgentSessionModel


class AgentSessionRepository(AgentSessionRepositoryABC):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, session: AgentSession) -> AgentSession:
        model = AgentSessionModel(
            id=session.id,
            todo_id=session.todo_id,
            phase_id=session.phase_id,
            agent_type=session.agent_type.value,
            external_session_id=session.external_session_id,
            status=session.status.value,
            task_context=session.task_context,
            result_summary=session.result_summary,
            error_reason=session.error_reason,
            started_at=session.started_at,
            completed_at=session.completed_at,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, session_id: uuid.UUID) -> AgentSession | None:
        result = await self.db.execute(
            select(AgentSessionModel).where(AgentSessionModel.id == session_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_phase_id(self, phase_id: uuid.UUID) -> AgentSession | None:
        result = await self.db.execute(
            select(AgentSessionModel)
            .where(AgentSessionModel.phase_id == phase_id)
            .order_by(AgentSessionModel.created_at.desc())
        )
        row = result.scalars().first()
        return self._to_entity(row) if row else None

    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[AgentSession]:
        result = await self.db.execute(
            select(AgentSessionModel)
            .where(AgentSessionModel.todo_id == todo_id)
            .order_by(AgentSessionModel.created_at)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def list_active(self) -> list[AgentSession]:
        result = await self.db.execute(
            select(AgentSessionModel).where(
                AgentSessionModel.status.in_(["pending", "running", "paused"])
            )
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def update(self, session: AgentSession) -> AgentSession:
        result = await self.db.execute(
            select(AgentSessionModel).where(AgentSessionModel.id == session.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"AgentSession {session.id} not found")
        model.status = session.status.value
        model.external_session_id = session.external_session_id
        model.task_context = session.task_context
        model.result_summary = session.result_summary
        model.error_reason = session.error_reason
        model.started_at = session.started_at
        model.completed_at = session.completed_at
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: AgentSessionModel) -> AgentSession:
        return AgentSession(
            id=model.id,
            todo_id=model.todo_id,
            phase_id=model.phase_id,
            agent_type=AgentType(model.agent_type),
            external_session_id=model.external_session_id or "",
            status=SessionStatus(model.status),
            task_context=model.task_context or {},
            result_summary=model.result_summary or {},
            error_reason=model.error_reason or "",
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

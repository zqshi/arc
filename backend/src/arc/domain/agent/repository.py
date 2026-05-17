from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.agent.entity import AgentSession


class AgentSessionRepository(ABC):
    @abstractmethod
    async def create(self, session: AgentSession) -> AgentSession: ...

    @abstractmethod
    async def get_by_id(self, session_id: uuid.UUID) -> AgentSession | None: ...

    @abstractmethod
    async def get_by_phase_id(self, phase_id: uuid.UUID) -> AgentSession | None: ...

    @abstractmethod
    async def list_by_todo_id(self, todo_id: uuid.UUID) -> list[AgentSession]: ...

    @abstractmethod
    async def list_active(self) -> list[AgentSession]: ...

    @abstractmethod
    async def update(self, session: AgentSession) -> AgentSession: ...

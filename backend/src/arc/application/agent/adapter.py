from __future__ import annotations

from abc import ABC, abstractmethod

from arc.domain.agent.value_objects import AgentType, SessionStatus

from .context_builder import TaskContext
from .events import AgentEvent


class CodingAgentAdapter(ABC):
    """Unified interface for all coding agent backends."""

    agent_type: AgentType

    @abstractmethod
    async def start(self, context: TaskContext) -> str:
        """Start agent execution. Returns the external session ID."""

    @abstractmethod
    async def get_status(self, session_id: str) -> SessionStatus:
        """Query current session status."""

    @abstractmethod
    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        """Fetch incremental events since the given event ID."""

    @abstractmethod
    async def cancel(self, session_id: str) -> None:
        """Cancel a running session."""

    @abstractmethod
    async def close(self) -> None:
        """Release underlying resources."""

    async def __aenter__(self) -> CodingAgentAdapter:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

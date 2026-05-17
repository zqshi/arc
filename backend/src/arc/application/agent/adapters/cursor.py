"""Cursor CLI adapter — skeleton for future implementation.

Cursor exposes a CLI interface for AI-assisted coding. This adapter will
spawn the Cursor CLI process and translate its output into AgentEvents.
"""

from __future__ import annotations

import logging

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)


class CursorAdapter(CodingAgentAdapter):
    agent_type = AgentType.CURSOR

    def __init__(self, cli_path: str = "cursor") -> None:
        self._cli_path = cli_path

    async def start(self, context: TaskContext) -> str:
        raise NotImplementedError("Cursor adapter not yet implemented")

    async def get_status(self, session_id: str) -> SessionStatus:
        raise NotImplementedError("Cursor adapter not yet implemented")

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        raise NotImplementedError("Cursor adapter not yet implemented")

    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError("Cursor adapter not yet implemented")

    async def close(self) -> None:
        pass

"""Codex API adapter — skeleton for future implementation.

Codex exposes an OpenAI-compatible API for code generation tasks.
This adapter will integrate with Codex's task submission and polling endpoints.
"""

from __future__ import annotations

import logging

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)


class CodexAdapter(CodingAgentAdapter):
    agent_type = AgentType.CODEX
    implemented = False

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1") -> None:
        self._api_key = api_key
        self._base_url = base_url

    async def start(self, context: TaskContext) -> str:
        raise NotImplementedError("Codex adapter not yet implemented")

    async def get_status(self, session_id: str) -> SessionStatus:
        raise NotImplementedError("Codex adapter not yet implemented")

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        raise NotImplementedError("Codex adapter not yet implemented")

    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError("Codex adapter not yet implemented")

    async def close(self) -> None:
        pass

from __future__ import annotations

import logging

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent, EventType
from arc.application.ai.openhands_client import (
    OpenHandsClient,
    OpenHandsSessionStatus,
    create_openhands_client,
)
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)

_STATUS_MAP: dict[OpenHandsSessionStatus, SessionStatus] = {
    OpenHandsSessionStatus.CREATED: SessionStatus.PENDING,
    OpenHandsSessionStatus.RUNNING: SessionStatus.RUNNING,
    OpenHandsSessionStatus.PAUSED: SessionStatus.PAUSED,
    OpenHandsSessionStatus.COMPLETED: SessionStatus.COMPLETED,
    OpenHandsSessionStatus.ERROR: SessionStatus.ERROR,
}

_EVENT_TYPE_MAP: dict[str, EventType] = {
    "action": EventType.ACTION,
    "observation": EventType.OBSERVATION,
    "status": EventType.STATUS,
}


class OpenHandsAdapter(CodingAgentAdapter):
    agent_type = AgentType.OPENHANDS

    def __init__(self, client: OpenHandsClient | None = None) -> None:
        self._client = client or create_openhands_client()
        self._owns_client = client is None

    async def start(self, context: TaskContext) -> str:
        # v6.17: skill 规范 + 工具指引经 to_markdown 注入 (OpenHands 自管工具集,
        # per-session MCP config 不支持, mcp 工具靠指引文本降级 — agent 自主遵循)
        session = await self._client.create_session()
        task_markdown = context.to_markdown()
        await self._client.send_task(session.session_id, task_markdown)
        logger.info("OpenHands session %s started for todo %s", session.session_id, context.todo_id)
        return session.session_id

    async def get_status(self, session_id: str) -> SessionStatus:
        oh_status = await self._client.get_status(session_id)
        return _STATUS_MAP.get(oh_status, SessionStatus.ERROR)

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        oh_events = await self._client.get_events(session_id, since_id=since)
        return [
            AgentEvent(
                event_id=e.id,
                event_type=_EVENT_TYPE_MAP.get(e.type, EventType.LOG),
                content=e.content,
                timestamp=e.timestamp,
                metadata=e.metadata,
            )
            for e in oh_events
            if e.content.strip()
        ]

    async def cancel(self, session_id: str) -> None:
        await self._client.stop_session(session_id)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.close()

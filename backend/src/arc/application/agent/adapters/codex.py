from __future__ import annotations

import json
import logging
import uuid

import httpx

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent, EventType
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)


class CodexAdapter(CodingAgentAdapter):
    agent_type = AgentType.CODEX
    implemented = True

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "codex-mini-latest",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client: httpx.AsyncClient | None = None
        self._sessions: dict[str, dict] = {}

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    async def start(self, context: TaskContext) -> str:
        session_id = str(uuid.uuid4())
        task_md = context.to_markdown()

        client = self._get_client()
        resp = await client.post(
            "/responses",
            json={
                "model": self._model,
                "instructions": "You are a coding agent. Complete the task described below. "
                "Write production-quality code following the project conventions.",
                "input": task_md,
                "tools": [{"type": "code_interpreter"}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

        self._sessions[session_id] = {
            "response_id": data.get("id", ""),
            "status": data.get("status", "queued"),
            "output": data.get("output", []),
            "events_sent": 0,
        }

        logger.info(
            "Codex session %s started (response_id=%s)",
            session_id,
            data.get("id"),
        )
        return session_id

    async def get_status(self, session_id: str) -> SessionStatus:
        session = self._sessions.get(session_id)
        if not session:
            return SessionStatus.ERROR

        response_id = session.get("response_id")
        if not response_id:
            return SessionStatus.ERROR

        try:
            client = self._get_client()
            resp = await client.get(f"/responses/{response_id}")
            resp.raise_for_status()
            data = resp.json()
            session["status"] = data.get("status", "unknown")
            session["output"] = data.get("output", [])
        except Exception as exc:
            logger.warning("Codex status poll failed: %s", exc)

        status_map = {
            "queued": SessionStatus.PENDING,
            "in_progress": SessionStatus.RUNNING,
            "completed": SessionStatus.COMPLETED,
            "failed": SessionStatus.ERROR,
            "cancelled": SessionStatus.CANCELLED,
        }
        return status_map.get(session["status"], SessionStatus.RUNNING)

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        session = self._sessions.get(session_id)
        if not session:
            return []

        output = session.get("output", [])
        sent = session.get("events_sent", 0)

        events: list[AgentEvent] = []
        for i, item in enumerate(output[sent:], start=sent):
            content = ""
            event_type = EventType.OBSERVATION

            if isinstance(item, dict):
                item_type = item.get("type", "")
                if item_type == "code_interpreter_call":
                    content = item.get("input", "")
                    event_type = EventType.ACTION
                elif item_type == "code_interpreter_call_output":
                    content = item.get("output", "")
                    event_type = EventType.OBSERVATION
                elif item_type == "message":
                    msg_content = item.get("content", [])
                    parts = []
                    for c in msg_content:
                        if isinstance(c, dict) and c.get("text"):
                            parts.append(c["text"])
                    content = "\n".join(parts) if parts else json.dumps(item, ensure_ascii=False)
                else:
                    content = json.dumps(item, ensure_ascii=False)
            else:
                content = str(item)

            if content.strip():
                events.append(
                    AgentEvent(
                        event_id=str(i),
                        event_type=event_type,
                        content=content,
                    )
                )

        session["events_sent"] = len(output)
        return events

    async def cancel(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        response_id = session.get("response_id")
        if not response_id:
            return

        try:
            client = self._get_client()
            await client.post(f"/responses/{response_id}/cancel")
        except Exception as exc:
            logger.warning("Codex cancel failed: %s", exc)

        session["status"] = "cancelled"

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        self._sessions.clear()

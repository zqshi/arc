"""Cursor `agent` CLI adapter.

Cursor exposes a standalone `agent` CLI (print mode `-p` for non-interactive
automation, text output). This adapter spawns the CLI process and translates
its stdout into AgentEvents. Structurally mirrors ClaudeCodeAdapter (CLI
subprocess + _Session state machine), without MCP config injection (Cursor
CLI has no --mcp-config flag — mcp tools degrade via to_markdown text) and
without JSON parsing (Cursor --output-format is text-only).

Refs:
- CLI: https://cursor.com/docs/cli (`agent -p "prompt" --model --mode --sandbox`)
- Pattern: application/agent/adapters/claude_code.py
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent, EventType
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)


@dataclass
class _Session:
    process: asyncio.subprocess.Process
    stdout_lines: list[str] = field(default_factory=list)
    stderr_lines: list[str] = field(default_factory=list)
    read_task: asyncio.Task | None = None
    finished: bool = False
    return_code: int | None = None


class CursorAdapter(CodingAgentAdapter):
    agent_type = AgentType.CURSOR
    implemented = True

    def __init__(
        self,
        cli_path: str = "agent",
        model: str = "",
        mode: str = "agent",
        work_dir: str = "",
    ) -> None:
        self._cli_path = cli_path
        self._model = model
        self._mode = mode
        self._work_dir = work_dir
        self._sessions: dict[str, _Session] = {}

    async def start(self, context: TaskContext) -> str:
        session_id = str(uuid.uuid4())

        cwd = self._work_dir or None
        if context.project_context:
            for line in context.project_context.splitlines():
                if line.startswith("工作目录:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        cwd = path
                    break

        # prompt 走 argv (-p); Cursor CLI 文档未支持 stdin 喂入。
        # task_md 通常数 KB, ARG_MAX 风险低; 超限留后续版本改临时文件。
        cmd = [self._cli_path, "-p", context.to_markdown()]
        if self._model:
            cmd.extend(["--model", self._model])
        if self._mode and self._mode != "agent":
            cmd.extend(["--mode", self._mode])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        session = _Session(process=process)
        self._sessions[session_id] = session

        session.read_task = asyncio.create_task(
            self._read_output(session_id),
            name=f"cursor-reader-{session_id}",
        )

        logger.info(
            "Cursor session %s started (pid=%s, cwd=%s)",
            session_id,
            process.pid,
            cwd,
        )
        return session_id

    async def _read_output(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        stdout = session.process.stdout
        stderr = session.process.stderr

        async def _drain_stderr():
            while True:
                line = await stderr.readline()
                if not line:
                    break
                session.stderr_lines.append(line.decode(errors="replace").rstrip())

        stderr_task = asyncio.create_task(_drain_stderr())

        while True:
            line = await stdout.readline()
            if not line:
                break
            session.stdout_lines.append(line.decode(errors="replace").rstrip())

        await stderr_task
        session.return_code = await session.process.wait()
        session.finished = True

    async def get_status(self, session_id: str) -> SessionStatus:
        session = self._sessions.get(session_id)
        if not session:
            return SessionStatus.ERROR

        if not session.finished:
            return SessionStatus.RUNNING

        if session.return_code == 0:
            return SessionStatus.COMPLETED
        return SessionStatus.ERROR

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        session = self._sessions.get(session_id)
        if not session:
            return []

        since_idx = 0
        if since:
            try:
                since_idx = int(since) + 1
            except ValueError:
                since_idx = 0

        events: list[AgentEvent] = []
        lines = session.stdout_lines[since_idx:]

        for i, line in enumerate(lines, start=since_idx):
            if not line.strip():
                continue
            events.append(
                AgentEvent(
                    event_id=str(i),
                    event_type=EventType.OBSERVATION,
                    content=line,
                )
            )

        if session.finished and session.stderr_lines:
            stderr_combined = "\n".join(session.stderr_lines[-20:])
            if stderr_combined.strip():
                events.append(
                    AgentEvent(
                        event_id=f"stderr-{session_id}",
                        event_type=EventType.LOG,
                        content=f"[stderr]\n{stderr_combined}",
                    )
                )
                session.stderr_lines.clear()

        return events

    async def cancel(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session or session.finished:
            return

        import signal

        try:
            session.process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(session.process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                session.process.kill()
                await session.process.wait()
        except ProcessLookupError:
            pass

        session.finished = True
        session.return_code = session.process.returncode
        logger.info("Cursor session %s cancelled", session_id)

    async def close(self) -> None:
        for sid in list(self._sessions):
            await self.cancel(sid)
            session = self._sessions.pop(sid, None)
            if session and session.read_task and not session.read_task.done():
                session.read_task.cancel()

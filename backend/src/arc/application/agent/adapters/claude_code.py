from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
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
    # v6.18: 本 session 的 mcp_config 临时文件路径 (None=无 MCP)。进程输出读完 /
    # close() 时删文件, 避免长期运行累积 arc-mcp-*.json 残留。
    mcp_config_path: str | None = None


class ClaudeCodeAdapter(CodingAgentAdapter):
    agent_type = AgentType.CLAUDE_CODE
    implemented = True

    def __init__(
        self,
        cli_path: str = "claude",
        work_dir: str = "",
        model: str = "",
    ) -> None:
        self._cli_path = cli_path
        self._work_dir = work_dir
        self._model = model
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

        cmd = [self._cli_path, "--print", "--output-format", "json"]
        if self._model:
            cmd.extend(["--model", self._model])
        # v6.17: MCP server 注入 (Claude Code 原生 --mcp-config, agent 直连 MCP server 调工具)
        mcp_config_path = self._write_mcp_config(context.mcp_servers)
        if mcp_config_path:
            cmd.extend(["--mcp-config", mcp_config_path])

        task_md = context.to_markdown()

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        process.stdin.write(task_md.encode())
        process.stdin.write_eof()

        session = _Session(process=process, mcp_config_path=mcp_config_path)
        self._sessions[session_id] = session

        session.read_task = asyncio.create_task(
            self._read_output(session_id),
            name=f"claude-code-reader-{session_id}",
        )

        logger.info(
            "Claude Code session %s started (pid=%s, cwd=%s)",
            session_id,
            process.pid,
            cwd,
        )
        return session_id

    @staticmethod
    def _write_mcp_config(mcp_servers: list[dict]) -> str | None:
        """构造 Claude Code mcpServers 配置, 写临时文件返回路径 (v6.17)。

        无 mcp_servers → None。stdio → {command, args, env}; http/sse → {type, url, headers}。
        临时文件路径会绑定到 _Session, 进程输出读完 / close() 时删除 (v6.18 生命周期清理)。
        """
        if not mcp_servers:
            return None
        servers: dict = {}
        for srv in mcp_servers:
            name = srv.get("name") or "mcp-server"
            transport = srv.get("transport", "stdio")
            if transport == "stdio":
                servers[name] = {
                    "command": srv.get("command"),
                    "args": srv.get("args") or [],
                    "env": srv.get("env") or {},
                }
            else:  # http / sse
                entry: dict = {"type": "http", "url": srv.get("url")}
                if srv.get("headers"):
                    entry["headers"] = srv["headers"]
                servers[name] = entry
        fd, path = tempfile.mkstemp(suffix=".json", prefix="arc-mcp-")
        with os.fdopen(fd, "w") as f:
            json.dump({"mcpServers": servers}, f)
        return path

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
        self._cleanup_mcp_config(session)

    @staticmethod
    def _cleanup_mcp_config(session: _Session) -> None:
        """删除 session 的 mcp_config 临时文件 (v6.18 生命周期清理)。

        进程输出读完或 close() 时调用。无文件/已删则静默跳过。
        """
        path = session.mcp_config_path
        if not path:
            return
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        session.mcp_config_path = None

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
            event = self._parse_line(line, str(i))
            if event:
                events.append(event)

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

    @staticmethod
    def _parse_line(line: str, event_id: str) -> AgentEvent | None:
        line = line.strip()
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return AgentEvent(
                event_id=event_id,
                event_type=EventType.LOG,
                content=line,
            )

        if isinstance(data, dict):
            content = data.get("result", "") or data.get("content", "") or data.get("text", "")
            if not content and "message" in data:
                content = data["message"]
            if not content:
                content = json.dumps(data, ensure_ascii=False)

            event_type = EventType.OBSERVATION
            if data.get("type") == "error":
                event_type = EventType.ERROR
            elif data.get("is_error"):
                event_type = EventType.ERROR

            return AgentEvent(
                event_id=event_id,
                event_type=event_type,
                content=content,
                metadata={k: v for k, v in data.items() if k not in ("result", "content", "text")},
            )

        return AgentEvent(
            event_id=event_id,
            event_type=EventType.LOG,
            content=str(data),
        )

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
        logger.info("Claude Code session %s cancelled", session_id)

    async def close(self) -> None:
        for sid in list(self._sessions):
            await self.cancel(sid)
            session = self._sessions.pop(sid, None)
            if session and session.read_task and not session.read_task.done():
                session.read_task.cancel()
            if session:
                self._cleanup_mcp_config(session)  # v6.18: 兜底删残留临时文件

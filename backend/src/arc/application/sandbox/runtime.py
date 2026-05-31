"""Sandbox runtime implementations.

Provides execution isolation for mutation tools (write_file, run_command).
Two implementations:

- ``ApprovalGateSandboxRuntime``: Pauses execution and requests user approval
  via WebSocket before running destructive operations. Zero infrastructure.
- ``DockerSandboxRuntime``: Executes inside a disposable Docker container
  with read-only project mount and tmpfs overlay. (Phase 1b)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arc.domain.sandbox.value_objects import SandboxPolicy

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    """A pending approval request awaiting user response."""

    request_id: str
    tool_name: str
    tool_input: dict
    future: asyncio.Future


class SandboxRuntime(ABC):
    """Abstract interface for sandbox execution backends."""

    @abstractmethod
    async def run_command(self, params: dict) -> str:
        """Execute a shell command within the sandbox."""

    @abstractmethod
    async def write_file(self, params: dict) -> str:
        """Write a file within the sandbox."""

    async def close(self) -> None:
        """Release sandbox resources."""


# ---------------------------------------------------------------------------
# Approval Gate — zero infrastructure, user-in-the-loop
# ---------------------------------------------------------------------------


class ApprovalGateSandboxRuntime(SandboxRuntime):
    """Pauses before destructive operations and asks the user for permission.

    The approval flow:
    1. Tool call arrives (write_file or run_command)
    2. Runtime emits an ``approval_required`` event via the callback
    3. Runtime awaits an asyncio.Future for the user's response
    4. If approved → executes directly on host (existing behavior)
    5. If rejected → returns error string to the LLM

    The WebSocket handler bridges user approval_response messages to
    the pending Future via ``respond(request_id, approved)``.
    """

    def __init__(
        self,
        policy: SandboxPolicy,
        project_path: str,
        *,
        emit_callback: Any = None,
        timeout_seconds: float = 120.0,
    ):
        self._policy = policy
        self._base_path = Path(project_path).expanduser().resolve()
        self._emit = emit_callback  # async callable(event_dict) -> None
        self._timeout = timeout_seconds
        self._pending: dict[str, asyncio.Future] = {}

    async def run_command(self, params: dict) -> str:
        if "run_command" in self._policy.approval_required_for:
            approved = await self._request_approval("run_command", params)
            if not approved:
                return "用户拒绝执行该命令。请换一种方式或解释为什么需要执行。"

        # Execute directly (same as tools.py _run_command)
        from arc.application.execution.tools import _run_command

        return await _run_command(params, base_path=self._base_path)

    async def write_file(self, params: dict) -> str:
        if "write_file" in self._policy.approval_required_for:
            approved = await self._request_approval("write_file", params)
            if not approved:
                return "用户拒绝写入该文件。请确认路径和内容是否合理。"

        from arc.application.execution.tools import _write_file

        return await _write_file(params, base_path=self._base_path)

    async def _request_approval(self, tool_name: str, tool_input: dict) -> bool:
        """Emit approval_required event and wait for user response."""
        request_id = str(uuid.uuid4())[:12]
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        # Notify frontend via callback
        if self._emit:
            await self._emit({
                "event": "approval_required",
                "request_id": request_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
            })

        try:
            approved = await asyncio.wait_for(future, timeout=self._timeout)
            return bool(approved)
        except asyncio.TimeoutError:
            logger.warning("Approval timeout for %s (request %s)", tool_name, request_id)
            return False
        finally:
            self._pending.pop(request_id, None)

    def respond(self, request_id: str, approved: bool) -> bool:
        """Resolve a pending approval future. Called by WS handler.

        Returns True if the request_id was found and resolved.
        """
        future = self._pending.get(request_id)
        if future and not future.done():
            future.set_result(approved)
            return True
        return False

    async def close(self) -> None:
        # Cancel any pending approvals
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
        self._pending.clear()


# ---------------------------------------------------------------------------
# Docker Sandbox — container isolation (Phase 1b, stub for now)
# ---------------------------------------------------------------------------


class DockerSandboxRuntime(SandboxRuntime):
    """Executes commands inside a disposable Docker container.

    Project directory is mounted read-only; writes go to a tmpfs overlay.
    Not yet implemented — raises NotImplementedError.
    """

    def __init__(self, policy: SandboxPolicy, project_path: str):
        self._policy = policy
        self._project_path = project_path

    async def run_command(self, params: dict) -> str:
        raise NotImplementedError(
            "Docker sandbox 尚未实现。请将 sandbox.mode 设为 'approval_gate' 或 'none'。"
        )

    async def write_file(self, params: dict) -> str:
        raise NotImplementedError(
            "Docker sandbox 尚未实现。请将 sandbox.mode 设为 'approval_gate' 或 'none'。"
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_sandbox_runtime(
    policy: SandboxPolicy,
    project_path: str,
    *,
    emit_callback: Any = None,
) -> SandboxRuntime:
    """Create the appropriate sandbox runtime from a policy."""
    from arc.domain.sandbox.value_objects import SandboxMode

    if policy.mode == SandboxMode.APPROVAL_GATE:
        return ApprovalGateSandboxRuntime(
            policy, project_path, emit_callback=emit_callback
        )
    if policy.mode == SandboxMode.DOCKER:
        return DockerSandboxRuntime(policy, project_path)

    raise ValueError(f"Unknown sandbox mode: {policy.mode}")

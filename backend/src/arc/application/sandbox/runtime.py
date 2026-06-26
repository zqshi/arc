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
import subprocess
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from arc.domain.sandbox.value_objects import SandboxPolicy

# Type alias for tool implementation functions injected from execution layer.
# Signature: (params: dict, *, base_path: Path) -> str
ToolImplFn = Callable[..., Awaitable[str]]

logger = logging.getLogger(__name__)

# v6.7: 审批响应跨 worker 路由的 bus channel 前缀
_SANDBOX_CHANNEL_PREFIX = "arc:sandbox:"


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
        conversation_id: str = "",
        emit_callback: Any = None,
        timeout_seconds: float = 120.0,
        run_command_impl: ToolImplFn | None = None,
        write_file_impl: ToolImplFn | None = None,
    ):
        self._policy = policy
        self._base_path = Path(project_path).expanduser().resolve()
        self._conversation_id = conversation_id
        self._emit = emit_callback  # async callable(event_dict) -> None
        self._timeout = timeout_seconds
        self._pending: dict[str, asyncio.Future] = {}
        self._run_command_impl = run_command_impl
        self._write_file_impl = write_file_impl
        self._monitor_task: asyncio.Task | None = None

    def _channel(self) -> str:
        return f"{_SANDBOX_CHANNEL_PREFIX}{self._conversation_id}"

    def _get_bus(self):
        """惰性取全局 EventBus (lifespan 注入); None=进程内无 bus。"""
        try:
            from arc.infrastructure.eventbus import get_global_bus

            return get_global_bus()
        except Exception:
            return None

    def _ensure_monitor(self) -> None:
        """启动 bus 监听 (懒启动, 多 worker 下审批响应跨进程路由)。

        监听 arc:sandbox:{cid} channel, 收到 {request_id, approved} 后
        本地 respond 解析 future (future 不可跨进程, 必须在持有 runtime
        的 worker 本地解析)。
        """
        if self._monitor_task is not None or not self._conversation_id:
            return
        bus = self._get_bus()
        if bus is None:
            return
        self._monitor_task = asyncio.create_task(self._monitor_approvals(bus))

    async def _monitor_approvals(self, bus) -> None:
        """监听 bus channel, 把审批响应路由到本地 respond。"""
        try:
            async for event in bus.subscribe(self._channel()):
                request_id = event.get("request_id")
                if request_id is None:
                    continue
                approved = event.get("approved", False)
                self.respond(request_id, bool(approved))
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("Approval monitor ended for %s: %s", self._conversation_id, exc)

    async def run_command(self, params: dict) -> str:
        if "run_command" in self._policy.approval_required_for:
            approved = await self._request_approval("run_command", params)
            if not approved:
                return "用户拒绝执行该命令。请换一种方式或解释为什么需要执行。"

        if self._run_command_impl is None:
            raise RuntimeError(
                "run_command_impl not injected. "
                "Pass it via create_sandbox_runtime()."
            )
        return await self._run_command_impl(params, base_path=self._base_path)

    async def write_file(self, params: dict) -> str:
        if "write_file" in self._policy.approval_required_for:
            approved = await self._request_approval("write_file", params)
            if not approved:
                return "用户拒绝写入该文件。请确认路径和内容是否合理。"

        if self._write_file_impl is None:
            raise RuntimeError(
                "write_file_impl not injected. "
                "Pass it via create_sandbox_runtime()."
            )
        return await self._write_file_impl(params, base_path=self._base_path)

    async def _request_approval(self, tool_name: str, tool_input: dict) -> bool:
        """Emit approval_required event and wait for user response."""
        self._ensure_monitor()
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
        # Cancel bus monitor (跨 worker 审批路由)
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        # Cancel any pending approvals
        for future in self._pending.values():
            if not future.done():
                future.set_result(False)
        self._pending.clear()


# ---------------------------------------------------------------------------
# Docker Sandbox — container isolation (v6.0.0 groundwork)
# ---------------------------------------------------------------------------


class DockerSandboxRuntime(SandboxRuntime):
    """在一次性 Docker 容器内执行命令。

    隔离模型 (v6.0.0):
    - 项目目录以**读写**方式挂载到容器 /workspace。构建产物 (如 dist) 必须持久化
      到宿主项目目录, 供 DeployService 读取——这与早期 stub 注释"只读+tmpfs"不同:
      tmpfs 会让产物随容器销毁丢失, 破坏部署链路。RW 挂载是正确取舍。
    - 容器仅能访问挂载的项目目录, 无其他宿主访问; 受 memory/network/timeout 限制。
    - write_file 直接写入宿主项目目录 (用户工作区, 经沙箱边界校验禁止逃逸),
      与容器通过挂载共享。run_command 的隔离是 Docker 模式的核心价值 (任意 shell)。

    配置来自 SandboxPolicy: docker_image / memory_limit_mb / network_enabled / timeout_seconds。
    每次调用 `docker run --rm` 自清理, 无持久容器资源。
    """

    def __init__(self, policy: SandboxPolicy, project_path: str):
        self._policy = policy
        self._project_path = str(Path(project_path).expanduser().resolve())

    async def run_command(self, params: dict) -> str:
        command = params["command"]
        requested_timeout = int(params.get("timeout", 30))
        # 同时受调用方请求与策略上限约束
        timeout = min(requested_timeout, self._policy.timeout_seconds)
        argv = self._build_docker_argv(command)
        return await asyncio.to_thread(self._exec, argv, timeout)

    async def write_file(self, params: dict) -> str:
        rel_path = params["path"]
        content = params["content"]

        try:
            target = self._resolve_path(rel_path)
        except ValueError as e:
            return f"错误: {e}"

        def _write():
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return f"已写入(沙箱): {rel_path} ({len(content)} 字符)"

        return await asyncio.to_thread(_write)

    def _build_docker_argv(self, command: str) -> list[str]:
        """构造 docker run 命令 (argv list, 避免 shell 注入)。

        command 作为 sh -c 的单一参数传入, 不参与 docker 调用的 shell 拼接。
        """
        p = self._policy
        argv: list[str] = [
            "docker", "run", "--rm",
            "-v", f"{self._project_path}:/workspace",
            "-w", "/workspace",
            "--memory", f"{p.memory_limit_mb}m",
        ]
        if not p.network_enabled:
            argv += ["--network", "none"]
        argv.append(p.docker_image)
        argv += ["sh", "-c", command]
        return argv

    def _resolve_path(self, rel_path: str) -> Path:
        """解析路径并校验沙箱边界 — 禁止逃逸出项目目录。"""
        base = Path(self._project_path)
        candidate = Path(rel_path)
        target = (
            (base / candidate).resolve()
            if not candidate.is_absolute()
            else candidate.resolve()
        )
        try:
            target.relative_to(base)
        except ValueError:
            raise ValueError(f"路径逃逸出项目目录: {rel_path}")
        return target

    def _exec(self, argv: list[str], timeout: int) -> str:
        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return f"命令超时 ({timeout}秒, docker)"
        except FileNotFoundError:
            return "错误: docker 未安装或不在 PATH 中"

        output_parts: list[str] = []
        if result.stdout:
            stdout = result.stdout[:10000]
            if len(result.stdout) > 10000:
                stdout += "\n... stdout 已截断 (超过 10000 字符)"
            output_parts.append(stdout)
        if result.stderr:
            stderr = result.stderr[:5000]
            if len(result.stderr) > 5000:
                stderr += "\n... stderr 已截断"
            output_parts.append(f"[stderr]\n{stderr}")
        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(output_parts) if output_parts else "(无输出)"

    async def close(self) -> None:
        # 每次调用 docker run --rm 自清理, 无持久资源需释放
        pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_sandbox_runtime(
    policy: SandboxPolicy,
    project_path: str,
    *,
    conversation_id: str = "",
    emit_callback: Any = None,
    run_command_impl: ToolImplFn | None = None,
    write_file_impl: ToolImplFn | None = None,
) -> SandboxRuntime:
    """Create the appropriate sandbox runtime from a policy.

    Args:
        conversation_id: 对话 ID (v6.7 审批链路: emit_callback 路由 +
            bus 监听 arc:sandbox:{cid} 跨 worker 路由审批响应)
        run_command_impl: Async function matching execution.tools._run_command
            signature. Injected by caller to avoid circular import with
            execution module.
        write_file_impl: Async function matching execution.tools._write_file
            signature. Injected by caller to avoid circular import with
            execution module.
    """
    from arc.domain.sandbox.value_objects import SandboxMode

    if policy.mode == SandboxMode.APPROVAL_GATE:
        return ApprovalGateSandboxRuntime(
            policy,
            project_path,
            conversation_id=conversation_id,
            emit_callback=emit_callback,
            run_command_impl=run_command_impl,
            write_file_impl=write_file_impl,
        )
    if policy.mode == SandboxMode.DOCKER:
        return DockerSandboxRuntime(policy, project_path)

    raise ValueError(f"Unknown sandbox mode: {policy.mode}")

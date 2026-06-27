"""OpenSandboxRuntime 适配器测试 (v6.7 全量多 worker)。

验证云沙箱后端: 沙箱即工作区 + sandbox_id 跨 worker 共享 (SandboxRegistry)。
首建 worker create+上传+注册 id; 其他 worker connect 复用跳过上传。
mock opensandbox SDK + registry, 不连真实 server/redis。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.sandbox.opensandbox_runtime import OpenSandboxRuntime


def _mock_execution(stdout: str = "", stderr: str = "", exit_code: int = 0):
    """构造 mock Execution (commands.run 返回值)。"""
    return SimpleNamespace(
        logs=SimpleNamespace(
            stdout=[SimpleNamespace(text=stdout)] if stdout else [],
            stderr=[SimpleNamespace(text=stderr)] if stderr else [],
        ),
        result=SimpleNamespace(exit_code=exit_code),
    )


@pytest.fixture
def mock_sandbox():
    """mock opensandbox.Sandbox + sandbox_registry + WriteEntry (首建路径: get 返回 None)。"""
    sb = AsyncMock()
    sb.sandbox_id = "sb-id-123"
    sb.commands = AsyncMock()
    sb.commands.run = AsyncMock(return_value=_mock_execution(stdout="ok\n"))
    sb.files = AsyncMock()
    sb.files.read_file = AsyncMock(return_value="file content")
    sb.files.write_files = AsyncMock(return_value=None)
    sb.close = AsyncMock()

    with (
        patch("arc.application.sandbox.opensandbox_runtime.Sandbox") as sandbox_cls,
        patch("arc.application.sandbox.opensandbox_runtime.sandbox_registry") as reg,
        patch("arc.application.sandbox.opensandbox_runtime.WriteEntry"),
    ):
        sandbox_cls.create = AsyncMock(return_value=sb)
        sandbox_cls.connect = AsyncMock(return_value=sb)
        reg.get = AsyncMock(return_value=None)  # 无已有 id → 走 create
        reg.set = AsyncMock()
        reg.remove = AsyncMock()
        yield sb, reg, sandbox_cls


class TestOpenSandboxRunCommand:
    @pytest.mark.asyncio
    async def test_run_command_executes_in_sandbox(self, mock_sandbox, tmp_path):
        sb, _, _ = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.run_command({"command": "echo hello", "timeout": 10})

        sb.commands.run.assert_called_once()
        assert "ok" in result
        await rt.close()

    @pytest.mark.asyncio
    async def test_run_command_lazy_creates_sandbox(self, mock_sandbox, tmp_path):
        """首建: get 返回 None → create + 上传 + 注册 id。"""
        sb, reg, sandbox_cls = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        sandbox_cls.create.assert_not_called()
        await rt.run_command({"command": "ls", "timeout": 10})
        sandbox_cls.create.assert_called_once()
        reg.set.assert_called_once_with("c1", "sb-id-123")  # 注册 id
        await rt.close()


class TestOpenSandboxConnectReuse:
    """全量多 worker: sandbox_id 共享, connect 复用。"""

    @pytest.mark.asyncio
    async def test_connect_reuses_existing_sandbox_skips_upload(self, mock_sandbox, tmp_path):
        """已有 id → connect 复用, 跳过项目上传。"""
        sb, reg, sandbox_cls = mock_sandbox
        reg.get = AsyncMock(return_value="existing-id")  # 其他 worker 已 create

        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c2",
            image="python:3.12-slim",
        )
        await rt.run_command({"command": "ls", "timeout": 10})

        # connect 而非 create
        sandbox_cls.connect.assert_called_once_with("existing-id")
        sandbox_cls.create.assert_not_called()
        # 复用 worker 不上传项目
        sb.files.write_files.assert_not_called()
        # 也不重复注册
        reg.set.assert_not_called()
        await rt.close()

    @pytest.mark.asyncio
    async def test_connect_id_cached_locally_no_reconnect(self, mock_sandbox, tmp_path):
        """同 runtime 内多次调用只 connect 一次 (本地缓存)。"""
        sb, reg, sandbox_cls = mock_sandbox
        reg.get = AsyncMock(return_value="existing-id")

        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c3",
            image="python:3.12-slim",
        )
        await rt.run_command({"command": "ls", "timeout": 10})
        await rt.run_command({"command": "pwd", "timeout": 10})

        sandbox_cls.connect.assert_called_once()  # 第二次用本地缓存
        await rt.close()


class TestOpenSandboxFiles:
    @pytest.mark.asyncio
    async def test_write_file_uploads_to_sandbox(self, mock_sandbox, tmp_path):
        sb, _, _ = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.write_file({"path": "src/main.py", "content": "print(1)"})

        sb.files.write_files.assert_called()
        assert result is not None
        await rt.close()

    @pytest.mark.asyncio
    async def test_read_file_reads_from_sandbox(self, mock_sandbox, tmp_path):
        sb, _, _ = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.read_file({"path": "README.md"})

        sb.files.read_file.assert_called_once_with("/workspace/README.md")
        assert "file content" in result
        await rt.close()


class TestOpenSandboxLifecycle:
    @pytest.mark.asyncio
    async def test_close_does_not_kill_shared_sandbox(self, mock_sandbox, tmp_path):
        """close 只断本地缓存, 不 kill 共享沙箱 (其他 worker 可能复用)。"""
        sb, _, _ = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        await rt.run_command({"command": "ls", "timeout": 10})
        await rt.close()

        sb.close.assert_not_called()  # 不 kill 共享沙箱

    @pytest.mark.asyncio
    async def test_close_without_create_is_noop(self, mock_sandbox, tmp_path):
        sb, _, _ = mock_sandbox
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        await rt.close()
        sb.close.assert_not_called()

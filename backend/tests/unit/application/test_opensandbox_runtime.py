"""OpenSandboxRuntime 适配器测试 (v6.7 波次3)。

验证云沙箱后端: 沙箱即工作区模式 (run_command/write_file/read_file 全走沙箱),
惰性创建 + 项目上传, close 释放。mock opensandbox SDK, 不连真实 server。
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
    """mock opensandbox.Sandbox, 拦截 create + 实例方法。"""
    sb = AsyncMock()
    sb.commands = AsyncMock()
    sb.commands.run = AsyncMock(return_value=_mock_execution(stdout="ok\n"))
    sb.files = AsyncMock()
    sb.files.read_file = AsyncMock(return_value="file content")
    sb.files.write_files = AsyncMock(return_value=None)
    sb.close = AsyncMock()

    with patch(
        "arc.application.sandbox.opensandbox_runtime.Sandbox"
    ) as sandbox_cls:
        sandbox_cls.create = AsyncMock(return_value=sb)
        yield sb


class TestOpenSandboxRunCommand:
    @pytest.mark.asyncio
    async def test_run_command_executes_in_sandbox(self, mock_sandbox, tmp_path):
        """run_command 在沙箱内执行, 返回 stdout。"""
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.run_command({"command": "echo hello", "timeout": 10})

        mock_sandbox.commands.run.assert_called_once()
        called_cmd = mock_sandbox.commands.run.call_args[0][0]
        assert "echo hello" in called_cmd
        assert "ok" in result
        await rt.close()

    @pytest.mark.asyncio
    async def test_run_command_lazy_creates_sandbox(self, mock_sandbox, tmp_path):
        """沙箱惰性创建: 构造时不 create, 首次 run_command 才 create。"""
        from arc.application.sandbox.opensandbox_runtime import Sandbox

        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        Sandbox.create.assert_not_called()  # 构造后未创建
        await rt.run_command({"command": "ls", "timeout": 10})
        Sandbox.create.assert_called_once()  # 首次调用才创建
        await rt.close()


class TestOpenSandboxFiles:
    @pytest.mark.asyncio
    async def test_write_file_uploads_to_sandbox(self, mock_sandbox, tmp_path):
        """write_file 经 sandbox.files.write_files 写入沙箱。"""
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.write_file({"path": "src/main.py", "content": "print(1)"})

        mock_sandbox.files.write_files.assert_called_once()
        entries = mock_sandbox.files.write_files.call_args[0][0]
        assert len(entries) == 1
        assert result is not None
        await rt.close()

    @pytest.mark.asyncio
    async def test_read_file_reads_from_sandbox(self, mock_sandbox, tmp_path):
        """read_file 从沙箱读取 (沙箱即工作区, 不读本地)。"""
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        result = await rt.read_file({"path": "README.md"})

        mock_sandbox.files.read_file.assert_called_once_with("/workspace/README.md")
        assert "file content" in result
        await rt.close()


class TestOpenSandboxLifecycle:
    @pytest.mark.asyncio
    async def test_close_releases_sandbox(self, mock_sandbox, tmp_path):
        """close 调 sandbox.close 释放沙箱资源。"""
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        await rt.run_command({"command": "ls", "timeout": 10})  # 触发创建
        await rt.close()

        mock_sandbox.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_create_is_noop(self, mock_sandbox, tmp_path):
        """未创建沙箱时 close 不抛 (noop)。"""
        rt = OpenSandboxRuntime(
            policy=MagicMock(mode=MagicMock(value="open_sandbox")),
            project_path=str(tmp_path),
            conversation_id="c1",
            image="python:3.12-slim",
        )
        await rt.close()  # 未触发创建, 不应抛
        mock_sandbox.close.assert_not_called()

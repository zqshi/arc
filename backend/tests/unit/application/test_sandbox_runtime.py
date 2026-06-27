"""Tests for application/sandbox runtime — ApprovalGateSandboxRuntime + DockerSandboxRuntime."""

import asyncio
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from arc.application.sandbox.runtime import (
    ApprovalGateSandboxRuntime,
    DockerSandboxRuntime,
)
from arc.domain.sandbox.value_objects import SandboxMode, SandboxPolicy


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10, check=True
        )
        return True
    except Exception:
        return False


DOCKER_AVAILABLE = _docker_available()


def _make_runtime():
    policy = SandboxPolicy(
        mode=SandboxMode.APPROVAL_GATE,
        approval_required_for=["run_command", "write_file"],
    )
    return ApprovalGateSandboxRuntime(policy=policy, project_path="/tmp/test")


class TestApprovalGateSandboxRuntime:
    def test_creation(self):
        rt = _make_runtime()
        assert rt is not None

    @pytest.mark.asyncio
    async def test_respond_unknown_request(self):
        rt = _make_runtime()
        result = rt.respond("nonexistent-id", True)
        assert result is False

    @pytest.mark.asyncio
    async def test_respond_resolves_future(self):
        rt = _make_runtime()
        req_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        rt._pending[req_id] = future

        rt.respond(req_id, True)
        assert future.done()
        assert future.result() is True

    @pytest.mark.asyncio
    async def test_respond_deny(self):
        rt = _make_runtime()
        req_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        rt._pending[req_id] = future

        rt.respond(req_id, False)
        assert future.result() is False

    @pytest.mark.asyncio
    async def test_close(self):
        rt = _make_runtime()
        await rt.close()


def _docker_policy(project_path: str) -> SandboxPolicy:
    """alpine:latest 最小镜像, 加快测试; network 关闭。"""
    return SandboxPolicy(
        mode=SandboxMode.DOCKER,
        docker_image="alpine:latest",
        memory_limit_mb=256,
        network_enabled=False,
        timeout_seconds=30,
    )


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker daemon 不可用")
class TestDockerSandboxRuntime:
    """v6.0.0 groundwork: 真实容器执行 + RW 挂载产物持久化。"""

    @pytest.mark.asyncio
    async def test_run_command_echo(self, tmp_path: Path):
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        result = await rt.run_command({"command": "echo hello-docker"})
        assert "hello-docker" in result
        assert "exit code" not in result  # 成功执行无错误码

    @pytest.mark.asyncio
    async def test_run_command_persists_artifact(self, tmp_path: Path):
        """核心: build 产物必须落宿主项目目录 (供 DeployService 读取)。"""
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        await rt.run_command(
            {"command": "mkdir -p dist && echo built > dist/index.html"}
        )
        artifact = tmp_path / "dist" / "index.html"
        assert artifact.exists()
        assert artifact.read_text().strip() == "built"

    @pytest.mark.asyncio
    async def test_write_file_creates(self, tmp_path: Path):
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        result = await rt.write_file({"path": "src/x.txt", "content": "hi"})
        assert "已写入" in result
        assert (tmp_path / "src" / "x.txt").read_text() == "hi"

    @pytest.mark.asyncio
    async def test_write_file_rejects_path_escape(self, tmp_path: Path):
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        result = await rt.write_file(
            {"path": "../../escape.txt", "content": "evil"}
        )
        assert "逃逸" in result
        assert not (tmp_path.parent.parent / "escape.txt").exists()

    @pytest.mark.asyncio
    async def test_run_command_timeout(self, tmp_path: Path):
        policy = SandboxPolicy(
            mode=SandboxMode.DOCKER,
            docker_image="alpine:latest",
            memory_limit_mb=256,
            network_enabled=False,
            timeout_seconds=30,
        )
        rt = DockerSandboxRuntime(policy, str(tmp_path))
        result = await rt.run_command({"command": "sleep 5", "timeout": 2})
        assert "超时" in result

    @pytest.mark.asyncio
    async def test_network_disabled(self, tmp_path: Path):
        """--network none: 容器内联网失败。"""
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        result = await rt.run_command(
            {"command": "wget -q -T2 -O- http://example.com; echo exit=$?"}
        )
        # 无网络 → wget 失败, exit code 非零
        assert "exit=0" not in result

    @pytest.mark.asyncio
    async def test_close_is_noop(self, tmp_path: Path):
        rt = DockerSandboxRuntime(_docker_policy(str(tmp_path)), str(tmp_path))
        await rt.close()  # 不应抛异常


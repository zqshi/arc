"""Tauri builder 镜像 smoke 测试 (slow, 需镜像已构建)。

验证 arc/tauri-builder:linux 镜像工具链可用 (cargo/node/tauri-cli) —
这是 v6.0 波次1 T6 的真实构建验证入口。镜像未构建时 skip
(CI 默认 skip, 本地 `cd src/arc/infrastructure/sandbox/images && make tauri-builder` 后手动 `pytest -m slow`)。

完整 `cargo tauri build` 端到端产物验证因耗时 (5-10 分钟) 留作手动步骤,
本 smoke 聚焦工具链可用性 (秒级)。
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from arc.application.sandbox.runtime import DockerSandboxRuntime
from arc.domain.sandbox.value_objects import SandboxMode, SandboxPolicy


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
        return True
    except Exception:
        return False


def _tauri_builder_available() -> bool:
    """arc/tauri-builder:linux 镜像是否已在本地 daemon 构建。"""
    if not _docker_available():
        return False
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", "arc/tauri-builder:linux"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


TAURI_BUILDER_AVAILABLE = _tauri_builder_available()


@pytest.mark.slow
@pytest.mark.skipif(
    not TAURI_BUILDER_AVAILABLE,
    reason="arc/tauri-builder:linux 未构建 (cd src/arc/infrastructure/sandbox/images && make tauri-builder)",
)
class TestTauriBuilderImage:
    """v6.0 波次1 T6: 构建工具链镜像可用性验证。"""

    @pytest.mark.asyncio
    async def test_toolchain_available(self, tmp_path):
        """镜像内 cargo / node / tauri-cli 均可用。

        tauri-cli 以 cargo 子命令形式安装 (cargo-tauri), 调用 `cargo tauri`。
        """
        policy = SandboxPolicy(
            mode=SandboxMode.DOCKER,
            docker_image="arc/tauri-builder:linux",
            memory_limit_mb=1024,
            network_enabled=False,
            timeout_seconds=60,
        )
        rt = DockerSandboxRuntime(policy, str(tmp_path))
        result = await rt.run_command(
            {"command": "cargo --version && node --version && cargo tauri --version"}
        )
        assert "cargo 1." in result, f"cargo 缺失: {result}"
        assert "v20." in result, f"node 缺失: {result}"
        assert "tauri-cli" in result, f"tauri-cli 缺失: {result}"
        assert "[exit code" not in result, f"命令失败: {result}"

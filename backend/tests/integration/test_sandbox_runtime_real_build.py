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
from arc.domain.sandbox.value_objects import BuildTarget, SandboxMode, SandboxPolicy


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


def _android_builder_available() -> bool:
    """arc/android-builder:linux 镜像是否已在本地 daemon 构建。"""
    if not _docker_available():
        return False
    try:
        r = subprocess.run(
            ["docker", "image", "inspect", "arc/android-builder:linux"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


ANDROID_BUILDER_AVAILABLE = _android_builder_available()


@pytest.mark.slow
@pytest.mark.skipif(
    not ANDROID_BUILDER_AVAILABLE,
    reason="arc/android-builder:linux 未构建 (cd src/arc/infrastructure/sandbox/images && make android-builder)",
)
class TestAndroidBuilderImage:
    """v6.12 波次3: android 构建工具链镜像可用性验证 (秒级 smoke)。

    完整 capacitor apk 构建 + apksigner 签名验证见 test_android_build_real.py (slow, 5min+)。
    """

    @pytest.mark.asyncio
    async def test_toolchain_available(self, tmp_path):
        """镜像内 capacitor / gradle / apksigner / keytool 均可用。

        build_target=CAPACITOR_APK 触发 L1 的 --shm-size 2g (argv 构造, 真实容器不报错)。
        """
        policy = SandboxPolicy(
            mode=SandboxMode.DOCKER,
            docker_image="arc/android-builder:linux",
            build_target=BuildTarget.CAPACITOR_APK,
            memory_limit_mb=1024,
            network_enabled=False,
            timeout_seconds=60,
        )
        rt = DockerSandboxRuntime(policy, str(tmp_path))
        result = await rt.run_command(
            {"command": "capacitor --version; gradle --version; ls /opt/android-sdk/build-tools/34.0.0/apksigner; which keytool"}
        )
        assert "7." in result, f"capacitor 缺失: {result}"
        assert "Gradle 8" in result, f"gradle 缺失: {result}"
        assert "apksigner" in result, f"apksigner 缺失: {result}"
        assert "keytool" in result, f"keytool 缺失: {result}"
        assert "[exit code" not in result, f"命令失败: {result}"

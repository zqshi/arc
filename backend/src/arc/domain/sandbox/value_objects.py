"""Sandbox domain value objects.

Defines the safety modes and policies for tool execution isolation.
Projects opt in to sandboxing via ``conversation_config["sandbox"]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SandboxMode(StrEnum):
    """How tool side-effects are isolated."""

    NONE = "none"  # Direct host execution (current default)
    APPROVAL_GATE = "approval_gate"  # Pause & ask user before mutating
    DOCKER = "docker"  # Execute inside a disposable container
    OPEN_SANDBOX = "open_sandbox"  # v6.7: 远程云沙箱 (OpenSandbox), 沙箱即工作区


class BuildTarget(StrEnum):
    """容器内构建目标 — 决定构建镜像 + build_command + artifact_path。

    与 ProjectType 正交: ProjectType 决定"构建什么形态", BuildTarget 决定
    "容器内构建到哪个目标"。镜像推导见 domain/sandbox/build_images.py。

    v6.0 波次1 激活 TAURI_LINUX; v6.12 波次2 激活 WEB, 波次3 激活 CAPACITOR_APK。
    """

    TAURI_LINUX = "tauri_linux"  # v6.0 波次1: tauri linux bundle (deb/AppImage)
    WEB = "web"  # v6.12 波次2: BINARY_APP web 资源构建 (npm run build → dist, 不打包原生客户端)
    CAPACITOR_APK = "capacitor_apk"  # v6.12 波次3: android apk (capacitor)


@dataclass(frozen=True)
class SandboxPolicy:
    """Per-project sandbox configuration.

    Loaded from ``Project.conversation_config["sandbox"]``.
    When ``mode`` is NONE, all other fields are ignored.

    build_target 记录构建目标语义 (供 BUILD_GUIDE/路由读取); 镜像解析在
    application 层完成 — 构造 SandboxPolicy 前由 resolve_build_image() 推导
    出 docker_image 填入, 故本类不耦合 ProjectType。
    """

    mode: SandboxMode = SandboxMode.NONE

    # Docker-specific
    docker_image: str = "python:3.12-slim"
    build_target: BuildTarget = BuildTarget.TAURI_LINUX
    timeout_seconds: int = 120
    memory_limit_mb: int = 512
    network_enabled: bool = False

    # OpenSandbox-specific (v6.7) — 云沙箱镜像, 空=用 config.opensandbox_image
    opensandbox_image: str = ""

    # Approval-gate-specific — which tools require user approval
    approval_required_for: list[str] = field(
        default_factory=lambda: ["write_file", "run_command"]
    )

    @classmethod
    def from_dict(cls, data: dict | None) -> SandboxPolicy:
        """Build a policy from a config dict (or return the default)."""
        if not data:
            return cls()
        mode_raw = data.get("mode", "none")
        try:
            mode = SandboxMode(mode_raw)
        except ValueError:
            mode = SandboxMode.NONE
        target_raw = data.get("target")
        try:
            build_target = (
                BuildTarget(target_raw) if target_raw else BuildTarget.TAURI_LINUX
            )
        except ValueError:
            build_target = BuildTarget.TAURI_LINUX
        return cls(
            mode=mode,
            docker_image=data.get("docker_image", cls.docker_image),
            build_target=build_target,
            timeout_seconds=data.get("timeout_seconds", cls.timeout_seconds),
            memory_limit_mb=data.get("memory_limit_mb", cls.memory_limit_mb),
            network_enabled=data.get("network_enabled", cls.network_enabled),
            opensandbox_image=data.get("opensandbox_image", ""),
            approval_required_for=data.get(
                "approval_required_for", ["write_file", "run_command"]
            ),
        )

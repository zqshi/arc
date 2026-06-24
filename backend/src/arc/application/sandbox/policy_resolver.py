"""Sandbox 策略解析 — 从 Project 实体解析最终 SandboxPolicy。

职责 (断点A/B 修复):
- B (mode): BINARY_APP 未显式配 sandbox 时, 默认启用容器化构建
  (mode=docker, target=tauri_linux) — 原生客户端构建依赖工具链镜像, 宿主直跑必失败
- A (image): mode=docker 且未显式配 docker_image 时, 按 (project_type, build_target)
  查 build_images 注册表推导; config.sandbox_builder_images 可覆盖

从 conversation_strategy._get_sandbox_policy 抽离, 便于单元测试 (纯 Project 输入, 无 db)。
"""
from __future__ import annotations

from arc.config import settings
from arc.domain.sandbox.build_images import (
    default_sandbox_config,
    resolve_build_image,
)
from arc.domain.sandbox.value_objects import (
    BuildTarget,
    SandboxMode,
    SandboxPolicy,
)


def resolve_sandbox_policy(project) -> SandboxPolicy | None:
    """从 Project 实体解析 sandbox 策略, 未启用时返回 None。"""
    sandbox_cfg = (project.conversation_config or {}).get("sandbox") or {}

    # BINARY_APP 未显式配 mode 时, 注入默认容器化构建
    if "mode" not in sandbox_cfg:
        default = default_sandbox_config(project.project_type)
        if default:
            sandbox_cfg = default

    if not sandbox_cfg or sandbox_cfg.get("mode", "none") == "none":
        return None

    # mode=docker 且未显式配镜像 → 按 (project_type, build_target) 推导
    if sandbox_cfg.get("mode") == SandboxMode.DOCKER.value and not sandbox_cfg.get(
        "docker_image"
    ):
        try:
            target = BuildTarget(
                sandbox_cfg.get("target", BuildTarget.TAURI_LINUX.value)
            )
        except ValueError:
            target = BuildTarget.TAURI_LINUX
        overrides = getattr(settings, "sandbox_builder_images", None) or None
        image = resolve_build_image(
            project.project_type, target, overrides=overrides
        )
        if image:
            sandbox_cfg = {**sandbox_cfg, "docker_image": image}

    return SandboxPolicy.from_dict(sandbox_cfg)

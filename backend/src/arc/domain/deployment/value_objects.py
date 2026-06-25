"""Deployment 值对象。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.domain.project.value_objects import ProjectType
    from arc.domain.sandbox.value_objects import BuildTarget


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    BUILDING = "building"
    UPLOADING = "uploading"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeployType(StrEnum):
    STATIC_SITE = "static_site"
    BINARY_ARTIFACT = "binary_artifact"  # 二进制制品(Tauri/Capacitor 产物) — v6.0.0


# 状态转换合法性表
VALID_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.PENDING: {DeploymentStatus.BUILDING},
    DeploymentStatus.BUILDING: {DeploymentStatus.UPLOADING, DeploymentStatus.FAILED},
    DeploymentStatus.UPLOADING: {DeploymentStatus.DEPLOYED, DeploymentStatus.FAILED},
    DeploymentStatus.DEPLOYED: {DeploymentStatus.ROLLED_BACK},
    DeploymentStatus.FAILED: set(),
    DeploymentStatus.ROLLED_BACK: set(),
}


@dataclass(frozen=True)
class DeployConfig:
    """部署配置值对象。"""

    build_command: str = "npm run build"
    artifact_path: str = "dist"
    cdn_domain: str | None = None

    @staticmethod
    def for_type(
        project_type: "ProjectType",
        build_target: "BuildTarget | None" = None,
    ) -> "DeployConfig":
        """按 (项目类型, 构建目标) 返回默认部署配置。

        build_target 默认 TAURI_LINUX (BINARY_APP 容器可构建主线)。
        ProjectType 与 BuildTarget 正交: 类型决定"构建什么形态",
        target 决定"容器内构建到哪个目标"。波次2/3 激活新 target 时在此加分支。
        """
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        target = build_target if build_target is not None else BuildTarget.TAURI_LINUX

        if project_type == ProjectType.STATIC_SITE:
            return DeployConfig(build_command="npm run build", artifact_path="dist")
        if project_type == ProjectType.BINARY_APP:
            # 原生客户端构建: 跨平台编译在容器内编排(见 sandbox runtime + build_images)。
            if target == BuildTarget.TAURI_LINUX:
                # tauri linux bundle (deb/AppImage), 产物落 src-tauri/target/release/bundle
                return DeployConfig(
                    build_command="cargo tauri build",
                    artifact_path="src-tauri/target/release/bundle",
                )
            # 波次2: target == WEB → npm run build (复用 static_site dist)
            # 波次3: target == CAPACITOR_APK → npx cap build android → android/app/build/outputs
        # 未识别类型走默认
        return DeployConfig()

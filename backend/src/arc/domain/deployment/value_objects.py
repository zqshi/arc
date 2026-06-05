"""Deployment 值对象。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DeploymentStatus(StrEnum):
    PENDING = "pending"
    BUILDING = "building"
    UPLOADING = "uploading"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DeployType(StrEnum):
    STATIC_SITE = "static_site"


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

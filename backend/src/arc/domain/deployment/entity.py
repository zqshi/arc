"""Deployment 实体 — 项目部署的生命周期管理。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.deployment.value_objects import (
    VALID_TRANSITIONS,
    DeployConfig,
    DeploymentStatus,
    DeployType,
)
from arc.domain.errors import DomainError


@dataclass
class Deployment:
    """一次部署的领域实体。"""

    project_id: uuid.UUID
    version_id: uuid.UUID
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    todo_id: uuid.UUID | None = None

    status: DeploymentStatus = DeploymentStatus.PENDING
    deploy_type: DeployType = DeployType.STATIC_SITE

    # 构建配置
    build_command: str = "npm run build"
    artifact_path: str = "dist"

    # 部署结果
    deploy_url: str | None = None
    storage_prefix: str | None = None
    files_uploaded: int = 0
    error_message: str | None = None

    # 生命周期
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    deployed_at: datetime | None = None

    # --- 状态转换行为 ---

    def _transition_to(self, target: DeploymentStatus) -> None:
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise DomainError(
                f"当前状态 {self.status.value} 不允许转换到 {target.value}"
            )
        self.status = target

    def start_build(self) -> None:
        self._transition_to(DeploymentStatus.BUILDING)

    def start_upload(self) -> None:
        self._transition_to(DeploymentStatus.UPLOADING)

    def complete(self, *, url: str, prefix: str, file_count: int) -> None:
        self._transition_to(DeploymentStatus.DEPLOYED)
        self.deploy_url = url
        self.storage_prefix = prefix
        self.files_uploaded = file_count
        self.deployed_at = datetime.now(UTC)

    def fail(self, reason: str) -> None:
        self._transition_to(DeploymentStatus.FAILED)
        self.error_message = reason

    def rollback(self) -> None:
        self._transition_to(DeploymentStatus.ROLLED_BACK)

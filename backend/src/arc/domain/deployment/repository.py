"""Deployment 仓储接口 — domain 层定义，infrastructure 层实现。"""
from __future__ import annotations

import uuid
from typing import Protocol

from arc.domain.deployment.entity import Deployment


class DeploymentRepository(Protocol):
    async def create(self, deployment: Deployment) -> Deployment: ...

    async def get_by_id(self, deployment_id: uuid.UUID) -> Deployment | None: ...

    async def get_latest_by_version(self, version_id: uuid.UUID) -> Deployment | None: ...

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Deployment]: ...

    async def update(self, deployment: Deployment) -> Deployment: ...

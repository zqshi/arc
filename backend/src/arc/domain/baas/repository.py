"""BaasInstance 仓储接口 — domain 层定义，infrastructure 层实现 (v5.6.0 T1)。"""
from __future__ import annotations

import uuid
from typing import Protocol

from arc.domain.baas.entity import BaasInstance


class BaasRepository(Protocol):
    async def create(self, instance: BaasInstance) -> BaasInstance: ...

    async def get_by_id(self, instance_id: uuid.UUID) -> BaasInstance | None: ...

    async def get_by_project(self, project_id: uuid.UUID) -> BaasInstance | None: ...

    async def update(self, instance: BaasInstance) -> BaasInstance: ...

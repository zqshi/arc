from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.capability.value_objects import (
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)


class AbstractCapabilityRepository(ABC):
    """能力声明仓储契约 (domain 定义, infrastructure 实现, W1.2)。

    按 type/status/scope 过滤查询 — service (W1.3) 据此支撑:
    - agent 迁移 (W2): list_capabilities(type=AGENT, status=ACTIVE, scope=GLOBAL)
    - 项目环节配置 (W3): list_capabilities(status=ACTIVE) 列可用能力
    """

    @abstractmethod
    async def create(self, capability: Capability) -> Capability: ...

    @abstractmethod
    async def get_by_id(self, capability_id: uuid.UUID) -> Capability | None: ...

    @abstractmethod
    async def get_by_name(self, name: str) -> Capability | None: ...

    @abstractmethod
    async def list_capabilities(
        self,
        *,
        type: CapabilityType | None = None,
        status: CapabilityStatus | None = None,
        scope: CapabilityScope | None = None,
    ) -> list[Capability]: ...

    @abstractmethod
    async def update(self, capability: Capability) -> Capability: ...

    @abstractmethod
    async def delete(self, capability_id: uuid.UUID) -> bool: ...

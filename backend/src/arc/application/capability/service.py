"""能力注册表服务 (v6.8.0 W1)。

CRUD + 启用/禁用 + 按 type/status/scope 查询。route 层只做参数校验,
业务逻辑 (同名冲突 + enum 转换 + 值对象不可变更新) 收敛于此。

与 template/service 同构: 直接注入 infrastructure repository (项目务实惯例)。
"""
from __future__ import annotations

import uuid
from dataclasses import replace

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.capability.value_objects import (
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)
from arc.domain.errors import ConflictError, NotFoundError
from arc.infrastructure.repositories.capability import CapabilityRepository


class CapabilityService:
    """能力声明管理 (agent/skill CRUD + 启用禁用)。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CapabilityRepository(db)

    async def create(
        self,
        *,
        name: str,
        type: str,
        config: dict,
        status: str,
        scope: str,
    ) -> Capability:
        existing = await self.repo.get_by_name(name)
        if existing:
            raise ConflictError(f"能力 name 已存在: {name}")
        capability = Capability(
            id=uuid.uuid4(),
            name=name,
            type=CapabilityType(type),
            config=config or {},
            status=CapabilityStatus(status) if status else CapabilityStatus.ACTIVE,
            scope=CapabilityScope(scope) if scope else CapabilityScope.GLOBAL,
        )
        return await self.repo.create(capability)

    async def get(self, capability_id: uuid.UUID) -> Capability:
        cap = await self.repo.get_by_id(capability_id)
        if not cap:
            raise NotFoundError("能力不存在")
        return cap

    async def list(
        self,
        *,
        type: str | None = None,
        status: str | None = None,
        scope: str | None = None,
    ) -> list[Capability]:
        return await self.repo.list_capabilities(
            type=CapabilityType(type) if type else None,
            status=CapabilityStatus(status) if status else None,
            scope=CapabilityScope(scope) if scope else None,
        )

    async def list_by_ids(
        self, capability_ids: list[uuid.UUID]
    ) -> list[Capability]:
        """按 id 批量取 (过滤不存在, 空列表返回空)。W3 注入/门禁共用。"""
        return await self.repo.list_by_ids(capability_ids)

    async def update(self, capability_id: uuid.UUID, updates: dict) -> Capability:
        cap = await self.get(capability_id)
        # 值对象不可变, 用 replace 创建变更实例 (type 不在更新字段, 保持不变)
        new_cap = replace(
            cap,
            name=updates.get("name", cap.name),
            config=updates.get("config", cap.config),
            status=CapabilityStatus(updates["status"]) if updates.get("status") else cap.status,
            scope=CapabilityScope(updates["scope"]) if updates.get("scope") else cap.scope,
        )
        return await self.repo.update(new_cap)

    async def delete(self, capability_id: uuid.UUID) -> None:
        deleted = await self.repo.delete(capability_id)
        if not deleted:
            raise NotFoundError("能力不存在")

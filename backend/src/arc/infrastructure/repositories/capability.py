"""CapabilityRepository 仓储实现 (v6.8.0 W1)。

继承 AbstractCapabilityRepository (domain 契约), infra 层用 SQLAlchemy 实现。
config JSONB ↔ dict 转换在 _to_entity / create / update 完成。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.capability.repository import AbstractCapabilityRepository
from arc.domain.capability.value_objects import (
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)
from arc.domain.errors import NotFoundError
from arc.infrastructure.models.capability import CapabilityModel


class CapabilityRepository(AbstractCapabilityRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, capability: Capability) -> Capability:
        model = CapabilityModel(
            id=capability.id,
            name=capability.name,
            type=capability.type.value,
            config=capability.config or None,
            status=capability.status.value,
            scope=capability.scope.value,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, capability_id: uuid.UUID) -> Capability | None:
        result = await self.db.execute(
            select(CapabilityModel).where(CapabilityModel.id == capability_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_name(self, name: str) -> Capability | None:
        """按 name 查首个匹配 (name 非 unique — 跨 scope 可能同名)。"""
        result = await self.db.execute(
            select(CapabilityModel).where(CapabilityModel.name == name).limit(1)
        )
        row = result.scalars().first()
        return self._to_entity(row) if row else None

    async def list_capabilities(
        self,
        *,
        type: CapabilityType | None = None,
        status: CapabilityStatus | None = None,
        scope: CapabilityScope | None = None,
    ) -> list[Capability]:
        stmt = select(CapabilityModel)
        if type is not None:
            stmt = stmt.where(CapabilityModel.type == type.value)
        if status is not None:
            stmt = stmt.where(CapabilityModel.status == status.value)
        if scope is not None:
            stmt = stmt.where(CapabilityModel.scope == scope.value)
        stmt = stmt.order_by(CapabilityModel.created_at.desc())
        result = await self.db.execute(stmt)
        return [self._to_entity(row) for row in result.scalars().all()]

    async def list_by_ids(
        self, capability_ids: list[uuid.UUID]
    ) -> list[Capability]:
        """按 id 列表批量取 (过滤不存在, 空列表返回空)。"""
        if not capability_ids:
            return []
        result = await self.db.execute(
            select(CapabilityModel).where(CapabilityModel.id.in_(capability_ids))
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, capability: Capability) -> Capability:
        result = await self.db.execute(
            select(CapabilityModel).where(CapabilityModel.id == capability.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise NotFoundError(f"能力不存在: {capability.id}")

        model.name = capability.name
        model.type = capability.type.value
        model.config = capability.config or None
        model.status = capability.status.value
        model.scope = capability.scope.value

        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def delete(self, capability_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(CapabilityModel).where(CapabilityModel.id == capability_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: CapabilityModel) -> Capability:
        return Capability(
            id=model.id,
            name=model.name,
            type=CapabilityType(model.type),
            config=model.config or {},
            status=CapabilityStatus(model.status),
            scope=CapabilityScope(model.scope),
        )

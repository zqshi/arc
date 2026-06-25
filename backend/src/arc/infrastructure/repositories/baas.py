"""BaasInstance 仓储实现 (v5.6.0 T7)。"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.baas.entity import BaasInstance
from arc.domain.baas.value_objects import BaasStatus
from arc.infrastructure.models.baas import BaasInstanceModel


class BaasRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, instance: BaasInstance) -> BaasInstance:
        model = BaasInstanceModel(
            id=instance.id,
            project_id=instance.project_id,
            schema_name=instance.schema_name,
            supabase_url=instance.supabase_url,
            status=instance.status.value,
            last_applied_model_version=instance.last_applied_model_version,
            activated_at=instance.activated_at,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, instance_id: uuid.UUID) -> BaasInstance | None:
        result = await self.db.execute(
            select(BaasInstanceModel).where(BaasInstanceModel.id == instance_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_project(self, project_id: uuid.UUID) -> BaasInstance | None:
        result = await self.db.execute(
            select(BaasInstanceModel).where(BaasInstanceModel.project_id == project_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def update(self, instance: BaasInstance) -> BaasInstance:
        result = await self.db.execute(
            select(BaasInstanceModel).where(BaasInstanceModel.id == instance.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"BaasInstance not found: {instance.id}")

        model.status = instance.status.value
        model.last_applied_model_version = instance.last_applied_model_version
        model.activated_at = instance.activated_at

        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: BaasInstanceModel) -> BaasInstance:
        return BaasInstance(
            id=model.id,
            project_id=model.project_id,
            schema_name=model.schema_name,
            supabase_url=model.supabase_url,
            status=BaasStatus(model.status),
            last_applied_model_version=model.last_applied_model_version,
            created_at=model.created_at,
            activated_at=model.activated_at,
        )

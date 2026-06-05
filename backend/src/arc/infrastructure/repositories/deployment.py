"""Deployment 仓储实现。"""
from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.value_objects import DeploymentStatus, DeployType
from arc.infrastructure.models.deployment import DeploymentModel


class DeploymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, deployment: Deployment) -> Deployment:
        model = DeploymentModel(
            id=deployment.id,
            project_id=deployment.project_id,
            version_id=deployment.version_id,
            todo_id=deployment.todo_id,
            status=deployment.status.value,
            deploy_type=deployment.deploy_type.value,
            build_command=deployment.build_command,
            artifact_path=deployment.artifact_path,
            deploy_url=deployment.deploy_url,
            storage_prefix=deployment.storage_prefix,
            files_uploaded=deployment.files_uploaded,
            error_message=deployment.error_message,
            deployed_at=deployment.deployed_at,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, deployment_id: uuid.UUID) -> Deployment | None:
        result = await self.db.execute(
            select(DeploymentModel).where(DeploymentModel.id == deployment_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_latest_by_version(self, version_id: uuid.UUID) -> Deployment | None:
        result = await self.db.execute(
            select(DeploymentModel)
            .where(DeploymentModel.version_id == version_id)
            .order_by(desc(DeploymentModel.created_at))
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Deployment]:
        result = await self.db.execute(
            select(DeploymentModel)
            .where(DeploymentModel.project_id == project_id)
            .order_by(desc(DeploymentModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, deployment: Deployment) -> Deployment:
        result = await self.db.execute(
            select(DeploymentModel).where(DeploymentModel.id == deployment.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Deployment not found: {deployment.id}")

        model.status = deployment.status.value
        model.deploy_url = deployment.deploy_url
        model.storage_prefix = deployment.storage_prefix
        model.files_uploaded = deployment.files_uploaded
        model.error_message = deployment.error_message
        model.deployed_at = deployment.deployed_at

        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: DeploymentModel) -> Deployment:
        return Deployment(
            id=model.id,
            project_id=model.project_id,
            version_id=model.version_id,
            todo_id=model.todo_id,
            status=DeploymentStatus(model.status),
            deploy_type=DeployType(model.deploy_type),
            build_command=model.build_command,
            artifact_path=model.artifact_path,
            deploy_url=model.deploy_url,
            storage_prefix=model.storage_prefix,
            files_uploaded=model.files_uploaded,
            error_message=model.error_message,
            created_at=model.created_at,
            deployed_at=model.deployed_at,
        )

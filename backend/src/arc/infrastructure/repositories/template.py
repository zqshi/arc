"""DomainTemplate 仓储实现 (v5.7.0 T3)。

含 pgvector 向量搜索 (与 Experience 同模式)。
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateScope,
    TemplateStatus,
)
from arc.infrastructure.models.template import DomainTemplateModel


class TemplateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, template: DomainTemplate) -> DomainTemplate:
        model = DomainTemplateModel(
            id=template.id,
            title=template.title,
            description=template.description,
            category=template.category.value,
            source_project_id=template.source_project_id,
            source_version_id=template.source_version_id,
            source_user_id=template.source_user_id,
            schema_template=template.schema_template or None,
            entity_patterns=template.entity_patterns or None,
            state_machine_patterns=template.state_machine_patterns or None,
            permission_patterns=template.permission_patterns or None,
            tags=template.tags or None,
            embedding=template.embedding,
            status=template.status.value,
            scope=template.scope.value,
            usage_count=template.usage_count,
            success_count=template.success_count,
            confidence=template.confidence,
            last_used_at=template.last_used_at,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(self, template_id: uuid.UUID) -> DomainTemplate | None:
        result = await self.db.execute(
            select(DomainTemplateModel).where(DomainTemplateModel.id == template_id)
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_user(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[DomainTemplate]:
        result = await self.db.execute(
            select(DomainTemplateModel)
            .where(DomainTemplateModel.source_user_id == user_id)
            .order_by(DomainTemplateModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def list_published(
        self, *, offset: int = 0, limit: int = 20
    ) -> list[DomainTemplate]:
        """列出已发布模板 (个人/组织可见, 排除 draft/deprecated)。"""
        result = await self.db.execute(
            select(DomainTemplateModel)
            .where(DomainTemplateModel.status == TemplateStatus.PUBLISHED.value)
            .order_by(DomainTemplateModel.usage_count.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, template: DomainTemplate) -> DomainTemplate:
        result = await self.db.execute(
            select(DomainTemplateModel).where(DomainTemplateModel.id == template.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"Template not found: {template.id}")

        model.title = template.title
        model.description = template.description
        model.status = template.status.value
        model.scope = template.scope.value
        model.usage_count = template.usage_count
        model.success_count = template.success_count
        model.confidence = template.confidence
        model.last_used_at = template.last_used_at
        model.schema_template = template.schema_template or None
        model.entity_patterns = template.entity_patterns or None
        model.tags = template.tags or None
        model.embedding = template.embedding

        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def search_by_embedding(
        self, embedding: list[float], *, limit: int = 10
    ) -> list[tuple[DomainTemplate, float]]:
        """向量相似度搜索 (仅 published 模板)。

        Returns:
            (template, similarity) 元组列表, similarity = 1 - cosine_distance (0..1)。
        """
        distance_col = DomainTemplateModel.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(DomainTemplateModel, distance_col)
            .where(DomainTemplateModel.embedding.isnot(None))
            .where(DomainTemplateModel.status == TemplateStatus.PUBLISHED.value)
            .order_by(distance_col)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [
            (self._to_entity(row), round(1 - distance, 4))
            for row, distance in result.all()
        ]

    @staticmethod
    def _to_entity(model: DomainTemplateModel) -> DomainTemplate:
        return DomainTemplate(
            id=model.id,
            title=model.title,
            description=model.description,
            category=TemplateCategory(model.category),
            source_project_id=model.source_project_id,
            source_version_id=model.source_version_id,
            source_user_id=model.source_user_id,
            schema_template=model.schema_template or {},
            entity_patterns=model.entity_patterns or [],
            state_machine_patterns=model.state_machine_patterns or [],
            permission_patterns=model.permission_patterns or [],
            tags=model.tags or [],
            embedding=model.embedding,
            status=TemplateStatus(model.status),
            scope=TemplateScope(model.scope),
            usage_count=model.usage_count,
            success_count=model.success_count,
            confidence=model.confidence,
            created_at=model.created_at,
            last_used_at=model.last_used_at,
        )

"""DomainTemplate 仓储接口 — domain 层定义, infrastructure 层实现 (v5.7.0 T1)。"""
from __future__ import annotations

import uuid
from typing import Protocol

from arc.domain.template.entity import DomainTemplate


class TemplateRepository(Protocol):
    async def create(self, template: DomainTemplate) -> DomainTemplate: ...

    async def get_by_id(self, template_id: uuid.UUID) -> DomainTemplate | None: ...

    async def list_by_user(
        self, user_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[DomainTemplate]: ...

    async def update(self, template: DomainTemplate) -> DomainTemplate: ...

    async def search_by_embedding(
        self, embedding: list[float], *, limit: int = 10
    ) -> list[DomainTemplate]:
        """语义相似度搜索 (向量距离排序)。"""
        ...

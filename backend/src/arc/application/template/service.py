"""模板 CRUD 服务 — 编辑 + 状态转换。

route 层只做参数校验, 模板变更的业务逻辑 (状态守卫 + 字段更新 + 状态机) 收敛于此。
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import ConflictError, NotFoundError
from arc.domain.template.value_objects import TemplateCategory, TemplateStatus
from arc.infrastructure.repositories.template import TemplateRepository

logger = logging.getLogger(__name__)


class TemplateService:
    """模板编辑与状态转换 (draft → confirmed → published → deprecated)。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TemplateRepository(db)

    async def update(self, template_id: uuid.UUID, updates: dict):
        """编辑模板元信息 (仅 draft 状态可编辑)。"""
        template = await self._get_or_raise(template_id)
        if template.status != TemplateStatus.DRAFT:
            raise ConflictError("仅 draft 状态模板可编辑")
        self._apply_updates(template, updates)
        return await self.repo.update(template)

    async def confirm(self, template_id: uuid.UUID):
        template = await self._get_or_raise(template_id)
        template.confirm()
        return await self.repo.update(template)

    async def publish(self, template_id: uuid.UUID):
        template = await self._get_or_raise(template_id)
        template.publish()
        return await self.repo.update(template)

    async def deprecate(self, template_id: uuid.UUID):
        template = await self._get_or_raise(template_id)
        template.deprecate()
        return await self.repo.update(template)

    async def _get_or_raise(self, template_id: uuid.UUID):
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise NotFoundError("Template not found")
        return template

    @staticmethod
    def _apply_updates(template, updates: dict) -> None:
        """将 update 字段映射到模板实体 (category 枚举转换, 其余直接赋值)。"""
        if updates.get("title") is not None:
            template.title = updates["title"]
        if updates.get("description") is not None:
            template.description = updates["description"]
        if updates.get("category") is not None:
            template.category = TemplateCategory(updates["category"])
        if updates.get("tags") is not None:
            template.tags = updates["tags"]

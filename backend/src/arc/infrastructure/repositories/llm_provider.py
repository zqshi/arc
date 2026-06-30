"""LLMProvider 仓储实现 (v6.20 L2)。

SqlAlchemy ORM + 用户级隔离。加解密在 application service 层注入 (entity.set_api_key(encrypt_fn)),
repo 只存取 api_key_enc 密文 token, 与签名凭证 (Project.enc_*_creds) 同构 — domain 不依赖
infrastructure/crypto, DDD 分层合规。

继承 domain LLMProviderRepository ABC (domain 定义契约, infrastructure 实现)。
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.llm.entity import LLMProvider
from arc.domain.llm.repository import LLMProviderRepository
from arc.domain.llm.value_objects import LLMProviderKind
from arc.infrastructure.models.llm_provider import LLMProviderModel


class SqlAlchemyLLMProviderRepository(LLMProviderRepository):
    """LLM provider 仓储 (用户级隔离, 所有查询带 user_id, 越权返回 None/False)。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, provider: LLMProvider) -> LLMProvider:
        model = LLMProviderModel(
            id=provider.id,
            user_id=provider.user_id,
            name=provider.name,
            kind=provider.kind.value,
            base_url=provider.base_url,
            api_key_enc=provider.api_key_enc,
            models=list(provider.models),
            is_default=provider.is_default,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def get_by_id(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> LLMProvider | None:
        result = await self.db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.id == provider_id,
                LLMProviderModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LLMProvider]:
        result = await self.db.execute(
            select(LLMProviderModel)
            .where(LLMProviderModel.user_id == user_id)
            .order_by(LLMProviderModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._to_entity(r) for r in result.scalars().all()]

    async def get_default(self, user_id: uuid.UUID) -> LLMProvider | None:
        result = await self.db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.user_id == user_id,
                LLMProviderModel.is_default.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def update(self, provider: LLMProvider) -> None:
        result = await self.db.execute(
            select(LLMProviderModel).where(LLMProviderModel.id == provider.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"LLMProvider not found: {provider.id}")
        model.name = provider.name
        model.kind = provider.kind.value
        model.base_url = provider.base_url
        model.api_key_enc = provider.api_key_enc
        model.models = list(provider.models)
        model.is_default = provider.is_default
        await self.db.flush()

    async def delete(self, provider_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.id == provider_id,
                LLMProviderModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    async def set_default(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """互斥设默认: 先清同用户其他 default (部分唯一索引保证至多一条), 再设此条。"""
        result = await self.db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.user_id == user_id,
                LLMProviderModel.is_default.is_(True),
            )
        )
        for other in result.scalars().all():
            other.is_default = False
        result = await self.db.execute(
            select(LLMProviderModel).where(
                LLMProviderModel.id == provider_id,
                LLMProviderModel.user_id == user_id,
            )
        )
        target = result.scalar_one_or_none()
        if target:
            target.is_default = True
        await self.db.flush()

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(LLMProviderModel)
            .where(LLMProviderModel.user_id == user_id)
        )
        return int(result.scalar_one())

    @staticmethod
    def _to_entity(model: LLMProviderModel) -> LLMProvider:
        return LLMProvider(
            id=model.id,
            user_id=model.user_id,
            name=model.name,
            kind=LLMProviderKind(model.kind),
            base_url=model.base_url,
            api_key_enc=model.api_key_enc,
            models=list(model.models or []),
            is_default=model.is_default,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

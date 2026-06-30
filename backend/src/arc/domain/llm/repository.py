"""LLM provider 仓储接口 — domain 契约 (v6.20 L1)。

infrastructure 层实现 (SqlAlchemy ORM + Fernet 加密)。与 AbstractProjectRepository 同构:
domain 定义契约, infrastructure 实现, 避免 domain 依赖具体实现。

用户级隔离: 所有查询带 user_id, 用户只能访问自己的厂商凭证 (越权访问他人凭证返回 None/False)。
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.llm.entity import LLMProvider


class LLMProviderRepository(ABC):
    """LLM provider 持久化契约 (用户级隔离)。"""

    @abstractmethod
    async def create(self, provider: LLMProvider) -> LLMProvider:
        """新建厂商凭证。"""
        ...

    @abstractmethod
    async def get_by_id(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> LLMProvider | None:
        """按 id 查 (带 user_id 鉴权, 越权返回 None)。"""
        ...

    @abstractmethod
    async def list_by_user(
        self,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[LLMProvider]:
        """列出某用户全部厂商凭证 (分页)。"""
        ...

    @abstractmethod
    async def get_default(self, user_id: uuid.UUID) -> LLMProvider | None:
        """取该用户全局默认凭证 (is_default=True, 无则 None)。"""
        ...

    @abstractmethod
    async def update(self, provider: LLMProvider) -> None:
        """更新厂商凭证。"""
        ...

    @abstractmethod
    async def delete(self, provider_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """删除 (带 user_id 鉴权, 越权返回 False)。"""
        ...

    @abstractmethod
    async def set_default(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """设为该用户全局默认 (互斥: 先清同用户其他 default, 再设此条)。"""
        ...

    @abstractmethod
    async def count_by_user(self, user_id: uuid.UUID) -> int:
        """该用户厂商凭证数量。"""
        ...

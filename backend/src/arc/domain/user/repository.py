from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.user.entity import User


class AbstractUserRepository(ABC):
    """Domain-level contract for user persistence."""

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_phone(self, phone: str) -> User | None: ...

    @abstractmethod
    async def create(self, entity: User) -> User: ...

    @abstractmethod
    async def update(self, entity: User) -> User: ...

    @abstractmethod
    async def is_empty(self) -> bool:
        """系统中是否无任何用户 (首用户特例判断, A1 投产门禁)。"""
        ...

    @abstractmethod
    async def count_admins(self) -> int:
        """系统中 ADMIN 用户数 (最后 admin 保护, A1 投产门禁)。"""
        ...

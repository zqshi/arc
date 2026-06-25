from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.user.entity import User as UserEntity
from arc.domain.user.repository import AbstractUserRepository
from arc.domain.user.value_objects import UserRole
from arc.infrastructure.models.user import UserModel


class UserRepository(AbstractUserRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> UserEntity | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_username(self, username: str) -> UserEntity | None:
        result = await self.db.execute(select(UserModel).where(UserModel.username == username))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_by_phone(self, phone: str) -> UserEntity | None:
        result = await self.db.execute(select(UserModel).where(UserModel.phone == phone))
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def create(self, entity: UserEntity) -> UserEntity:
        model = UserModel(
            id=entity.id,
            username=entity.username,
            phone=entity.phone,
            hashed_password=entity.hashed_password,
            display_name=entity.display_name,
            is_active=entity.is_active,
            role=entity.role.value,
        )
        self.db.add(model)
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    async def update(self, entity: UserEntity) -> UserEntity:
        result = await self.db.execute(select(UserModel).where(UserModel.id == entity.id))
        model = result.scalar_one_or_none()
        if not model:
            raise ValueError(f"User {entity.id} not found")
        model.username = entity.username
        model.phone = entity.phone
        model.hashed_password = entity.hashed_password
        model.display_name = entity.display_name
        model.is_active = entity.is_active
        model.role = entity.role.value
        await self.db.flush()
        await self.db.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: UserModel) -> UserEntity:
        return UserEntity(
            id=model.id,
            username=model.username,
            phone=model.phone,
            hashed_password=model.hashed_password,
            display_name=model.display_name,
            is_active=model.is_active,
            role=UserRole(model.role) if model.role else UserRole.ADMIN,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

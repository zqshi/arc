from __future__ import annotations

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import AuthenticationError
from arc.domain.user.entity import User as UserEntity
from arc.infrastructure.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> UserEntity:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("未提供认证信息")

    token = authorization[7:]

    from arc.application.auth.jwt import verify_access_token
    payload = verify_access_token(token)

    from arc.infrastructure.repositories.user import UserRepository
    user = await UserRepository(db).get_by_id(UUID(payload["sub"]))
    if not user or not user.is_active:
        raise AuthenticationError("用户不存在或已禁用")
    return user


CurrentUser = Annotated[UserEntity, Depends(get_current_user)]

from __future__ import annotations

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, Path
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import AuthenticationError
from arc.domain.user.entity import User as UserEntity
from arc.domain.user.value_objects import UserRole
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


_ROLE_LEVEL = {UserRole.VIEWER: 0, UserRole.MEMBER: 1, UserRole.ADMIN: 2}


def require_project_role(min_role: UserRole = UserRole.VIEWER):
    async def _check(
        project_id: UUID = Path(...),
        user: UserEntity = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> UserEntity:
        from sqlalchemy import select

        from arc.infrastructure.models.project import ProjectModel

        result = await db.execute(select(ProjectModel.user_id).where(ProjectModel.id == project_id))
        owner_id = result.scalar_one_or_none()
        if owner_id and owner_id == user.id:
            return user

        from arc.infrastructure.repositories.project_member import ProjectMemberRepository

        member_repo = ProjectMemberRepository(db)
        member = await member_repo.get_member(project_id, user.id)
        if not member:
            raise AuthenticationError("无权访问该项目")

        member_role = UserRole(member.role)
        if _ROLE_LEVEL.get(member_role, 0) < _ROLE_LEVEL.get(min_role, 0):
            raise AuthenticationError(f"需要 {min_role.value} 及以上权限")

        return user

    return Depends(_check)

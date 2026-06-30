from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from arc.application.auth.password import hash_password, verify_password
from arc.application.auth.sms import SMSService
from arc.application.organization.service import OrganizationService
from arc.domain.errors import AuthenticationError, ConflictError, ForbiddenError, NotFoundError
from arc.domain.user.entity import User
from arc.domain.user.value_objects import UserRole
from arc.infrastructure.models.user import RevokedTokenModel
from arc.infrastructure.repositories.organization import OrganizationMemberRepository
from arc.infrastructure.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.sms = SMSService.get_instance()
        self.org_svc = OrganizationService(db)
        self.org_member_repo = OrganizationMemberRepository(db)

    async def _role_for_new_user(self) -> UserRole:
        """首用户特例 (A1 投产门禁): 系统无用户时新注册者即 ADMIN, 否则 MEMBER。"""
        return UserRole.ADMIN if await self.user_repo.is_empty() else UserRole.MEMBER

    async def register_with_password(
        self, username: str, password: str, display_name: str | None = None
    ) -> User:
        existing = await self.user_repo.get_by_username(username)
        if existing:
            raise ConflictError("用户名已存在")

        user = User(
            username=username,
            hashed_password=hash_password(password),
            display_name=display_name or username,
            role=await self._role_for_new_user(),
        )
        user = await self.user_repo.create(user)
        await self.org_svc.create_org(
            name=f"{user.display_name}的工作区",
            owner_id=user.id,
        )
        return user

    async def register_with_phone(self, phone: str, display_name: str | None = None) -> User:
        existing = await self.user_repo.get_by_phone(phone)
        if existing:
            raise ConflictError("该手机号已注册")

        user = User(
            phone=phone,
            display_name=display_name or f"用户{phone[-4:]}",
            role=await self._role_for_new_user(),
        )
        user = await self.user_repo.create(user)
        await self.org_svc.create_org(
            name=f"{user.display_name}的工作区",
            owner_id=user.id,
        )
        return user

    async def login_with_password(self, username: str, password: str) -> dict:
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise AuthenticationError("用户名或密码错误")
        if not user.hashed_password:
            raise AuthenticationError("该账号未设置密码，请使用其他方式登录")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("用户名或密码错误")
        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        return await self._generate_tokens(user)

    async def send_sms_code(self, phone: str) -> None:
        await self.sms.send_code(phone)
        logger.info("SMS code sent to ***%s", phone[-4:])

    async def login_with_sms(self, phone: str, code: str) -> dict:
        valid = await self.sms.verify_code(phone, code)
        if not valid:
            raise AuthenticationError("验证码错误或已过期")

        user = await self.user_repo.get_by_phone(phone)
        if not user:
            user = User(
                phone=phone,
                display_name=f"用户{phone[-4:]}",
                role=await self._role_for_new_user(),
            )
            user = await self.user_repo.create(user)
            await self.org_svc.create_org(
                name=f"{user.display_name}的工作区",
                owner_id=user.id,
            )

        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        return await self._generate_tokens(user)

    async def refresh_token(self, refresh_token_str: str) -> dict:
        payload = verify_refresh_token(refresh_token_str)
        user_id = payload["sub"]
        jti = payload.get("jti")

        if jti and await self._is_revoked(jti):
            raise AuthenticationError("Token 已被撤销")

        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise AuthenticationError("用户不存在或已禁用")
        org_id = await self.get_default_org_id(user.id)
        access_token = create_access_token(str(user.id), user.username, org_id=org_id)
        return {"access_token": access_token, "token_type": "bearer"}

    async def logout(self, refresh_token_str: str) -> None:
        """Revoke the given refresh token."""
        try:
            payload = verify_refresh_token(refresh_token_str)
        except AuthenticationError:
            return
        jti = payload.get("jti")
        if not jti:
            return
        user_id = payload["sub"]
        exp = payload.get("exp", 0)
        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        await self._revoke_jti(jti, UUID(user_id), expires_at)

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    async def change_user_role(
        self, target_id: UUID, new_role: UserRole, actor: User
    ) -> User:
        """A1 投产门禁: admin 变更用户角色 + 最后 admin 保护。"""
        if not actor.has_permission(UserRole.ADMIN):
            raise ForbiddenError("仅管理员可变更用户角色")
        target = await self.user_repo.get_by_id(target_id)
        if not target:
            raise NotFoundError("用户不存在")
        # 最后 admin 保护: 不允许把最后一个 admin 降级为非 admin
        if target.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            if await self.user_repo.count_admins() <= 1:
                raise ForbiddenError("不能降级最后一个管理员")
        target.change_role(new_role)
        return await self.user_repo.update(target)

    async def _generate_tokens(self, user: User) -> dict:
        org_id = await self.get_default_org_id(user.id)
        access_token = create_access_token(str(user.id), user.username, org_id=org_id)
        refresh_token_str, _jti = create_refresh_token(str(user.id))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "phone": user.phone,
                "display_name": user.display_name,
                "role": user.role.value,
            },
            "org_id": org_id,
        }

    async def get_default_org_id(self, user_id: UUID) -> str | None:
        memberships = await self.org_member_repo.list_orgs_for_user(user_id)
        if memberships:
            return str(memberships[0].organization_id)
        return None

    async def _is_revoked(self, jti: str) -> bool:
        result = await self.db.execute(
            select(RevokedTokenModel).where(RevokedTokenModel.jti == jti)
        )
        return result.scalar_one_or_none() is not None

    async def _revoke_jti(self, jti: str, user_id: UUID, expires_at: datetime) -> None:
        if await self._is_revoked(jti):
            return
        model = RevokedTokenModel(jti=jti, user_id=user_id, expires_at=expires_at)
        self.db.add(model)
        await self.db.flush()

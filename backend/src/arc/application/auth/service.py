from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from arc.application.auth.password import hash_password, verify_password
from arc.application.auth.sms import SMSService
from arc.domain.errors import AuthenticationError, ConflictError
from arc.domain.user.entity import User
from arc.infrastructure.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.sms = SMSService.get_instance()

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
        )
        return await self.user_repo.create(user)

    async def register_with_phone(
        self, phone: str, display_name: str | None = None
    ) -> User:
        existing = await self.user_repo.get_by_phone(phone)
        if existing:
            raise ConflictError("该手机号已注册")

        user = User(
            phone=phone,
            display_name=display_name or f"用户{phone[-4:]}",
        )
        return await self.user_repo.create(user)

    async def login_with_password(
        self, username: str, password: str
    ) -> dict:
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise AuthenticationError("用户名或密码错误")
        if not user.hashed_password:
            raise AuthenticationError("该账号未设置密码，请使用其他方式登录")
        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("用户名或密码错误")
        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        return self._generate_tokens(user)

    async def send_sms_code(self, phone: str) -> None:
        code = await self.sms.send_code(phone)
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
            )
            user = await self.user_repo.create(user)

        if not user.is_active:
            raise AuthenticationError("账号已被禁用")

        return self._generate_tokens(user)

    async def refresh_token(self, refresh_token: str) -> dict:
        payload = verify_refresh_token(refresh_token)
        user_id = payload["sub"]
        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise AuthenticationError("用户不存在或已禁用")
        access_token = create_access_token(str(user.id), user.username)
        return {"access_token": access_token, "token_type": "bearer"}

    async def get_user(self, user_id: UUID) -> User | None:
        return await self.user_repo.get_by_id(user_id)

    def _generate_tokens(self, user: User) -> dict:
        access_token = create_access_token(str(user.id), user.username)
        refresh_token = create_refresh_token(str(user.id))
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "username": user.username,
                "phone": user.phone,
                "display_name": user.display_name,
                "role": user.role.value,
            },
        }

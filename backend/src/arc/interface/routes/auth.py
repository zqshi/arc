from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from arc.application.auth.service import AuthService
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    SMSLoginRequest,
    SMSSendRequest,
    TokenResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: DbSession):
    if not req.username and not req.phone:
        raise HTTPException(400, "请提供用户名或手机号")

    svc = AuthService(db)

    if req.username:
        if not req.password:
            raise HTTPException(400, "账号注册需要提供密码")
        user = await svc.register_with_password(
            req.username, req.password, req.display_name
        )
        result = svc._generate_tokens(user)
    else:
        user = await svc.register_with_phone(req.phone, req.display_name)
        result = svc._generate_tokens(user)

    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(**result["user"]),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: DbSession):
    svc = AuthService(db)
    result = await svc.login_with_password(req.username, req.password)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(**result["user"]),
    )


@router.post("/sms/send", status_code=204)
async def send_sms(req: SMSSendRequest, db: DbSession):
    svc = AuthService(db)
    await svc.send_sms_code(req.phone)


@router.post("/sms/login", response_model=TokenResponse)
async def sms_login(req: SMSLoginRequest, db: DbSession):
    svc = AuthService(db)
    result = await svc.login_with_sms(req.phone, req.code)
    return TokenResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
        user=UserResponse(**result["user"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: DbSession):
    svc = AuthService(db)
    result = await svc.refresh_token(req.refresh_token)
    return TokenResponse(access_token=result["access_token"])


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    return UserResponse(
        id=str(user.id),
        username=user.username,
        phone=user.phone,
        display_name=user.display_name,
    )

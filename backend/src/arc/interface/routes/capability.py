"""能力管理 API (v6.8.0 W1)。

全局能力 (agent/skill) 声明 CRUD。写操作 (create/update/delete) 需 admin;
读操作 (list/get) 登录即可 (项目环节配置需查询可用能力)。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.application.capability.service import CapabilityService
from arc.domain.errors import AppError, DomainError, ForbiddenError
from arc.domain.user.value_objects import UserRole
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.capability import (
    CapabilityCreateRequest,
    CapabilityResponse,
    CapabilityUpdateRequest,
)

router = APIRouter()


def _to_response(cap) -> CapabilityResponse:
    return CapabilityResponse(
        id=str(cap.id),
        name=cap.name,
        type=cap.type.value,
        config=cap.config or {},
        status=cap.status.value,
        scope=cap.scope.value,
    )


def _require_admin(user) -> None:
    if not user.has_permission(UserRole.ADMIN):
        raise ForbiddenError("需要管理员权限管理能力")


@router.get("", response_model=list[CapabilityResponse])
async def list_capabilities(
    db: DbSession,
    user: CurrentUser,
    type: str | None = Query(None),
    status: str | None = Query(None),
    scope: str | None = Query(None),
    skip: int = 0,
    limit: int = 100,
):
    """列出能力 (可按 type/status/scope 过滤, skip/limit 分页)。"""
    svc = CapabilityService(db)
    caps = await svc.list(type=type, status=status, scope=scope)
    return [_to_response(c) for c in caps[skip : skip + min(limit, 100)]]


@router.post("", response_model=CapabilityResponse, status_code=201)
async def create_capability(
    req: CapabilityCreateRequest, db: DbSession, user: CurrentUser
):
    _require_admin(user)
    svc = CapabilityService(db)
    try:
        cap = await svc.create(
            name=req.name,
            type=req.type,
            config=req.config,
            status=req.status,
            scope=req.scope,
        )
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(400, str(e))
    return _to_response(cap)


@router.get("/{capability_id}", response_model=CapabilityResponse)
async def get_capability(capability_id: uuid.UUID, db: DbSession, user: CurrentUser):
    svc = CapabilityService(db)
    try:
        cap = await svc.get(capability_id)
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    return _to_response(cap)


@router.patch("/{capability_id}", response_model=CapabilityResponse)
async def update_capability(
    capability_id: uuid.UUID,
    req: CapabilityUpdateRequest,
    db: DbSession,
    user: CurrentUser,
):
    _require_admin(user)
    svc = CapabilityService(db)
    try:
        cap = await svc.update(capability_id, req.model_dump(exclude_unset=True))
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(400, str(e))
    return _to_response(cap)


@router.delete("/{capability_id}")
async def delete_capability(capability_id: uuid.UUID, db: DbSession, user: CurrentUser):
    _require_admin(user)
    svc = CapabilityService(db)
    try:
        await svc.delete(capability_id)
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    return {"status": "deleted", "id": str(capability_id)}

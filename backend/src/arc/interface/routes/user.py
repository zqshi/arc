"""用户管理 API (A1 投产门禁)。

admin 可变更用户角色 (提权/降级), 含最后 admin 保护。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from arc.application.auth.service import AuthService
from arc.domain.user.value_objects import UserRole
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.auth import UserResponse, UserRoleUpdateRequest

router = APIRouter()


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    req: UserRoleUpdateRequest,
    db: DbSession,
    user: CurrentUser,
):
    """admin 变更用户角色 (A1 投产门禁: 含最后 admin 保护)。"""
    svc = AuthService(db)
    target = await svc.change_user_role(user_id, UserRole(req.role), user)
    return UserResponse(
        id=str(target.id),
        username=target.username,
        phone=target.phone,
        display_name=target.display_name,
        role=target.role.value,
    )

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from arc.domain.user.entity import User as UserEntity
from arc.domain.user.value_objects import UserRole
from arc.infrastructure.repositories.project import ProjectRepository
from arc.interface.deps import CurrentUser, DbSession, require_project_role
from arc.interface.schemas.project import (
    AddMemberRequest,
    MemberResponse,
    UpdateMemberRoleRequest,
)

router = APIRouter()


# ── Members ──────────────────────────────────────────────


@router.get("/{project_id}/members", response_model=list[MemberResponse])
async def list_members(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    member_repo = ProjectMemberRepository(db)
    members = await member_repo.list_members(project_id)
    return [
        MemberResponse(
            user_id=str(m.user_id),
            display_name=m.display_name,
            username=m.username,
            role=m.role,
            joined_at=m.joined_at.isoformat(),
        )
        for m in members
    ]


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    project_id: uuid.UUID,
    body: AddMemberRequest,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository
    from arc.infrastructure.repositories.user import UserRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    target_user_id = uuid.UUID(body.user_id)

    user_repo = UserRepository(db)
    target_user = await user_repo.get_by_id(target_user_id)
    if not target_user:
        raise HTTPException(404, "用户不存在")

    member_repo = ProjectMemberRepository(db)
    existing = await member_repo.get_member(project_id, target_user_id)
    if existing:
        raise HTTPException(409, "该用户已是项目成员")

    await member_repo.add_member(project_id, target_user_id, body.role)
    return MemberResponse(
        user_id=str(target_user.id),
        display_name=target_user.display_name,
        username=target_user.username,
        role=body.role,
        joined_at=datetime.now(UTC).isoformat(),
    )


@router.patch("/{project_id}/members/{member_user_id}", response_model=MemberResponse)
async def update_member_role(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository
    from arc.infrastructure.repositories.user import UserRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    member_repo = ProjectMemberRepository(db)
    updated = await member_repo.update_role(project_id, member_user_id, body.role)
    if not updated:
        raise HTTPException(404, "成员不存在")

    user_repo = UserRepository(db)
    target_user = await user_repo.get_by_id(member_user_id)
    member = await member_repo.get_member(project_id, member_user_id)
    return MemberResponse(
        user_id=str(member_user_id),
        display_name=target_user.display_name if target_user else "",
        username=target_user.username if target_user else None,
        role=body.role,
        joined_at=member.created_at.isoformat() if member else "",
    )


@router.delete("/{project_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    project_id: uuid.UUID,
    member_user_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    if member_user_id == user.id:
        raise HTTPException(400, "不能移除自己")

    member_repo = ProjectMemberRepository(db)
    removed = await member_repo.remove_member(project_id, member_user_id)
    if not removed:
        raise HTTPException(404, "成员不存在")

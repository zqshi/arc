"""项目签名/分发凭证配置 API (T2)。

接通零调用方的 infrastructure/crypto.encrypt + Project.set_*_creds,
与读取链路 (load_*_creds_for_project) 闭环。

权限: require_project_role(ADMIN) — 仅项目 owner/admin 可配置敏感凭证。
响应不回传明文, 只返回 configured 状态。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from arc.application.deployment.service import DeployService
from arc.domain.deployment.distributor import DistributorType
from arc.domain.deployment.signer import SignerType
from arc.domain.user.entity import User as UserEntity
from arc.domain.user.value_objects import UserRole
from arc.interface.deps import CurrentUser, DbSession, require_project_role
from arc.interface.schemas.project import (
    CredentialsStatusResponse,
    DistributionCredsUpdate,
    SigningCredsUpdate,
)

router = APIRouter()


@router.get("/{project_id}/credentials", response_model=CredentialsStatusResponse)
async def list_credentials(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    _viewer: UserEntity = require_project_role(),
):
    """列出各平台/渠道凭证配置状态 (mask 明文)。"""
    svc = DeployService(db)
    return await svc.list_credentials(project_id, user_id=user.id)


@router.put("/{project_id}/credentials/signing/{platform}")
async def configure_signing_creds(
    project_id: uuid.UUID,
    platform: SignerType,
    body: SigningCredsUpdate,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    """配置某平台签名凭证 (Apple/Windows/Android)。空 creds 不改变现有配置。"""
    svc = DeployService(db)
    return await svc.configure_signing_creds(
        project_id, platform, body.creds, user_id=user.id
    )


@router.put("/{project_id}/credentials/distribution/{channel}")
async def configure_distribution_creds(
    project_id: uuid.UUID,
    channel: DistributorType,
    body: DistributionCredsUpdate,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    """配置某渠道分发凭证 (AppStore/PlayStore/Tauri)。空 creds 不改变现有配置。"""
    svc = DeployService(db)
    return await svc.configure_distribution_creds(
        project_id, channel, body.creds, user_id=user.id
    )

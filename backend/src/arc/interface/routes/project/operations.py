from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from arc.domain.user.entity import User as UserEntity
from arc.domain.user.value_objects import UserRole
from arc.infrastructure.models.project import ProjectModel
from arc.infrastructure.repositories.project import (
    ProjectRepository,
)
from arc.interface.deps import CurrentUser, DbSession, require_project_role
from arc.interface.schemas.project import PhaseCapabilitiesUpdate

router = APIRouter()


# ── Domain Model ────────────────────────────────────────────


@router.get("/{project_id}/domain-model")
async def get_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    return await svc.get_domain_model(project, user.id)


@router.post("/{project_id}/domain-model/refresh")
async def refresh_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    merged, dm = await svc.refresh_domain_model(project, user.id)
    return {"merged": merged, "domain_model": dm}


@router.post("/{project_id}/domain-model/extract-from-code")
async def extract_domain_model_from_code(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Extract domain model directly from codebase source files."""
    from arc.application.project.domain_model_service import DomainModelService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DomainModelService(db)
    try:
        dm = await svc.extract_from_code(project)
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    return {"domain_model": dm}


@router.post("/{project_id}/domain-model/validate")
async def validate_domain_model_route(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    dm = project.domain_model or {}

    from arc.application.review.service import ReviewService
    from arc.infrastructure.repositories.review import ReviewFeedbackRepository

    feedback_repo = ReviewFeedbackRepository(db)
    svc = ReviewService(feedback_repo)
    feedbacks, result = await svc.validate_and_persist(project_id, dm)

    result["feedbacks_created"] = len(feedbacks)
    result["reviewed_model_version"] = dm.get("version", 0)
    return result


@router.put("/{project_id}/domain-model")
async def update_domain_model(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.domain_model = body
    project.updated_at = datetime.now(UTC)
    await repo.update(project)
    return project.domain_model


# ── Mode Switch & Delete ──────────────────────────────────


@router.get("/{project_id}/mode-switch-impact")
async def mode_switch_impact(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.todo import TodoRepository

    repo = TodoRepository(db)
    active_todos, _ = await repo.list_all(project_id=project_id, user_id=user.id, limit=1000)
    active_count = sum(1 for t in active_todos if t.status.value == "active")
    pending_count = sum(1 for t in active_todos if t.status.value == "pending")
    return {
        "active_count": active_count,
        "pending_count": pending_count,
        "safe_to_switch": active_count == 0,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    project.soft_delete()
    await repo.update(project)
    await db.commit()


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """恢复逻辑删除的项目。"""
    repo = ProjectRepository(db)
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    model = result.scalar_one_or_none()
    if not model or model.status != "deleted":
        raise HTTPException(404, "Deleted project not found")
    project = repo._to_entity(model)
    project.restore()
    await repo.update(project)
    await db.commit()
    from arc.interface.routes.project._helpers import _project_resp
    return _project_resp(project)


# ── Deployment (v5.5.0: 暴露 rollback 入口) ────────────────


def _parse_manifest(raw: str | None) -> dict:
    """解析 distribution_manifest JSON (非法/空 → 空 dict)。"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}


def _deployment_resp(deployment) -> dict:
    """Deployment 实体 → 响应 dict (含分发清单 T5)。"""
    manifest = _parse_manifest(deployment.distribution_manifest)
    return {
        "id": str(deployment.id),
        "project_id": str(deployment.project_id),
        "version_id": str(deployment.version_id),
        "todo_id": str(deployment.todo_id) if deployment.todo_id else None,
        "status": (
            deployment.status.value
            if hasattr(deployment.status, "value") else str(deployment.status)
        ),
        "deploy_type": (
            deployment.deploy_type.value
            if hasattr(deployment.deploy_type, "value") else str(deployment.deploy_type)
        ),
        "deploy_url": deployment.deploy_url,
        "storage_prefix": deployment.storage_prefix,
        "files_uploaded": deployment.files_uploaded,
        "error_message": deployment.error_message,
        "distribution_manifest": manifest,
        "download_page_url": manifest.get("download_page_url", ""),
        "created_at": deployment.created_at.isoformat() if deployment.created_at else None,
        "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
    }


@router.get("/{project_id}/deployments")
async def list_deployments(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
):
    """列出项目部署历史（分页）。"""
    from arc.application.deployment.service import DeployService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DeployService(db)
    deployments = await svc.list_deployments(
        project_id, offset=skip, limit=min(limit, 100)
    )
    return {"items": [_deployment_resp(d) for d in deployments], "skip": skip, "limit": limit}


@router.get("/{project_id}/versions/{version_id}/deployment/latest")
async def get_latest_deployment(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """获取版本最新一次部署记录（供前端 rollback 入口判断状态）。"""
    from arc.application.deployment.service import DeployService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DeployService(db)
    deployment = await svc.get_latest_deployment(version_id)
    if not deployment:
        raise HTTPException(404, "No deployment found for this version")
    return _deployment_resp(deployment)


@router.post("/{project_id}/deployments/{deployment_id}/rollback")
async def rollback_deployment(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """回滚指定部署（标记状态为 rolled_back，不删除文件）。

    v5.5.0: 暴露此前只在 service 层存在的 rollback_deployment，前端 RollbackButton 调用。
    """
    from arc.application.deployment.service import DeployService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = DeployService(db)
    deployment = await svc.rollback_deployment(deployment_id)
    return _deployment_resp(deployment)


@router.get("/{project_id}/deployments/{deployment_id}/manifest")
async def get_distribution_manifest(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """获取部署的分发清单 (v6.2.0 T5: 产物+签名+渠道结果, Arc 前端发布页用)。"""
    from arc.infrastructure.repositories.deployment import DeploymentRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    deployment = await DeploymentRepository(db).get_by_id(deployment_id)
    if not deployment:
        raise HTTPException(404, "Deployment not found")
    return _deployment_resp(deployment)


# ── Phase Capabilities (v6.8.0 W3) — 环节级能力配置 ──────────────


@router.put("/{project_id}/pipeline/phase-capabilities")
async def update_phase_capabilities(
    project_id: uuid.UUID,
    body: PhaseCapabilitiesUpdate,
    db: DbSession,
    user: CurrentUser,
    _admin: UserEntity = require_project_role(UserRole.ADMIN),
):
    """配置某环节启用的能力 (仅 admin)。

    非法 phase→400 (DomainError), capability 不存在→404, 禁用→409。
    """
    from arc.application.project.workspace_service import ProjectWorkspaceService

    svc = ProjectWorkspaceService(db)
    project = await svc.update_phase_capabilities(
        project_id, body.phase, body.capability_ids, user_id=user.id
    )
    return {"phase_capabilities": project.pipeline_config.get("phase_capabilities", {})}

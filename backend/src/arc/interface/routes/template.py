"""模板管理 API (v5.7.0 T9)。

CRUD + 语义搜索 + apply。复用 domain/application 层服务。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from arc.application.baas.service import BaasService
from arc.application.template.apply_service import TemplateApplyService
from arc.application.template.matching_service import TemplateMatchingService
from arc.application.template.service import TemplateService
from arc.domain.errors import AppError, DomainError
from arc.domain.template.value_objects import TemplateStatus
from arc.infrastructure.repositories.template import TemplateRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.template import (
    TemplateApplyRequest,
    TemplateResponse,
    TemplateSearchRequest,
    TemplateUpdateRequest,
)

router = APIRouter()


def _to_response(template) -> TemplateResponse:
    return TemplateResponse(
        id=str(template.id),
        title=template.title,
        description=template.description,
        category=template.category.value,
        source_project_id=str(template.source_project_id) if template.source_project_id else None,
        source_version_id=str(template.source_version_id) if template.source_version_id else None,
        source_user_id=str(template.source_user_id),
        schema_template=template.schema_template or {},
        entity_patterns=template.entity_patterns or [],
        state_machine_patterns=template.state_machine_patterns or [],
        permission_patterns=template.permission_patterns or [],
        tags=template.tags or [],
        status=template.status.value,
        scope=template.scope.value,
        usage_count=template.usage_count,
        success_count=template.success_count,
        success_rate=template.success_rate,
        confidence=template.confidence,
        created_at=template.created_at.isoformat() if template.created_at else None,
        last_used_at=template.last_used_at.isoformat() if template.last_used_at else None,
    )


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    db: DbSession, user: CurrentUser, skip: int = 0, limit: int = 20,
):
    """列出当前用户的模板 (按创建时间倒序)。"""
    repo = TemplateRepository(db)
    templates = await repo.list_by_user(user.id, offset=skip, limit=min(limit, 100))
    return [_to_response(t) for t in templates]


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: uuid.UUID, db: DbSession, user: CurrentUser):
    repo = TemplateRepository(db)
    template = await repo.get_by_id(template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    return _to_response(template)


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID, req: TemplateUpdateRequest, db: DbSession, user: CurrentUser,
):
    """编辑模板元信息 (仅 draft 状态)。"""
    svc = TemplateService(db)
    try:
        updated = await svc.update(template_id, req.model_dump(exclude_unset=True))
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(409, str(e))
    return _to_response(updated)


@router.post("/{template_id}/confirm", response_model=TemplateResponse)
async def confirm_template(template_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """确认 draft 模板 (draft → confirmed)。"""
    svc = TemplateService(db)
    try:
        template = await svc.confirm(template_id)
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(409, str(e))
    return _to_response(template)


@router.post("/{template_id}/publish", response_model=TemplateResponse)
async def publish_template(template_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """发布模板 (confirmed → published, 团队可见)。"""
    svc = TemplateService(db)
    try:
        template = await svc.publish(template_id)
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(409, str(e))
    return _to_response(template)


@router.post("/{template_id}/deprecate", response_model=TemplateResponse)
async def deprecate_template(template_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """废弃模板 (→ deprecated, 终态)。"""
    svc = TemplateService(db)
    try:
        template = await svc.deprecate(template_id)
    except AppError as e:
        raise HTTPException(e.status_code, e.detail)
    except (ValueError, DomainError) as e:
        raise HTTPException(409, str(e))
    return _to_response(template)


@router.post("/search", response_model=list[TemplateResponse])
async def search_templates(
    req: TemplateSearchRequest, db: DbSession, user: CurrentUser,
):
    """语义搜索已发布模板。"""
    repo = TemplateRepository(db)
    svc = TemplateMatchingService(repo)
    results = await svc.search_matching(req.query, limit=req.limit)
    return [_to_response(t) for t, _ in results]


@router.post("/apply")
async def apply_template(req: TemplateApplyRequest, db: DbSession, user: CurrentUser):
    """选中模板 apply 到新项目 Supabase (适配 + provision + apply)。"""
    repo = TemplateRepository(db)
    template = await repo.get_by_id(uuid.UUID(req.template_id))
    if not template:
        raise HTTPException(404, "Template not found")
    if template.status != TemplateStatus.PUBLISHED:
        raise HTTPException(409, "仅 published 模板可 apply")

    baas_service = BaasService(db)
    apply_svc = TemplateApplyService(baas_service, repo)
    try:
        await apply_svc.apply_template(
            template=template,
            requirement=req.requirement,
            project_id=uuid.UUID(req.project_id),
            supabase_url=req.supabase_url,
            model_version=req.model_version,
        )
    except (ValueError, DomainError) as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"apply 失败: {e}")
    return {"status": "applied", "template_id": str(template.id)}

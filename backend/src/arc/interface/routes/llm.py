"""LLM provider CRUD + 探活 API (v6.20 L6)。

用户级多厂商 LLM 凭证管理 (替代 config.py 固定字段)。挂 /api/llm, CurrentUser 鉴权。
api_key 加密存储 (Fernet), GET 不回明文 (只返 api_key_set)。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from arc.application.llm.service import LLMProviderService
from arc.domain.llm.value_objects import PROVIDER_TEMPLATES, LLMProviderKind
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.llm import (
    ListModelsResponse,
    LLMProviderCreate,
    LLMProviderResponse,
    LLMProviderUpdate,
    ProviderTemplateResponse,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter()


def _to_response(provider) -> LLMProviderResponse:
    return LLMProviderResponse(
        id=str(provider.id),
        name=provider.name,
        kind=provider.kind.value,
        base_url=provider.base_url,
        models=list(provider.models),
        is_default=provider.is_default,
        api_key_set=provider.has_api_key(),
    )


@router.get("/providers/templates", response_model=list[ProviderTemplateResponse])
async def list_provider_templates(user: CurrentUser):
    """预置 provider 模板 (单一真相源, 替代前端硬编码)。"""
    return [
        ProviderTemplateResponse(
            key=t.key,
            label=t.label,
            kind=t.kind.value,
            default_base_url=t.default_base_url,
            supports_list_models=t.kind.supports_list_models,
            suggested_models=list(t.suggested_models),
        )
        for t in PROVIDER_TEMPLATES
    ]


@router.get("/providers", response_model=list[LLMProviderResponse])
async def list_providers(
    db: DbSession,
    user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """列出当前用户全部 LLM 厂商凭证 (分页, 不回 api_key 明文)。"""
    svc = LLMProviderService(db)
    providers = await svc.list(user.id, skip=skip, limit=limit)
    return [_to_response(p) for p in providers]


@router.post("/providers", response_model=LLMProviderResponse)
async def create_provider(body: LLMProviderCreate, db: DbSession, user: CurrentUser):
    """新建 LLM 厂商凭证 (api_key Fernet 加密存储)。"""
    svc = LLMProviderService(db)
    try:
        provider = await svc.create(
            user_id=user.id,
            name=body.name,
            kind=LLMProviderKind(body.kind),
            base_url=body.base_url,
            api_key=body.api_key,
            is_default=body.is_default,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return _to_response(provider)


@router.patch("/providers/{provider_id}", response_model=LLMProviderResponse)
async def update_provider(
    provider_id: uuid.UUID, body: LLMProviderUpdate, db: DbSession, user: CurrentUser
):
    """更新厂商凭证 (api_key 留空不改; is_default=True 互斥切换)。"""
    svc = LLMProviderService(db)
    try:
        provider = await svc.update(
            provider_id,
            user.id,
            name=body.name,
            base_url=body.base_url,
            api_key=body.api_key,
            is_default=body.is_default,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return _to_response(provider)


@router.delete("/providers/{provider_id}")
async def delete_provider(
    provider_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    """删除厂商凭证 (用户级隔离, 越权 404)。"""
    svc = LLMProviderService(db)
    deleted = await svc.delete(provider_id, user.id)
    if not deleted:
        raise HTTPException(404, "LLMProvider not found")
    return {"status": "deleted"}


@router.post("/providers/verify", response_model=VerifyResponse)
async def verify_credentials(body: VerifyRequest, db: DbSession, user: CurrentUser):
    """探活临时凭证 (前端传未保存的 key+base_url), 成功顺带返模型清单。

    不读已存 settings, 验"正在编辑"的凭证, 不依赖保存顺序。
    """
    svc = LLMProviderService(db)
    result = await svc.verify_credentials(
        kind=LLMProviderKind(body.kind),
        base_url=body.base_url,
        api_key=body.api_key,
    )
    return VerifyResponse(
        valid=result.valid,
        models=list(result.models),
        error_kind=result.error_kind,
        error_message=result.error_message,
    )


@router.get("/providers/{provider_id}/models", response_model=ListModelsResponse)
async def list_models(
    provider_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    refresh: bool = Query(False),
):
    """读已存凭证模型清单 (缓存), ?refresh=true 重新拉取回填。"""
    svc = LLMProviderService(db)
    try:
        models = await svc.list_models(provider_id, user.id, refresh=refresh)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return ListModelsResponse(models=models, cached=not refresh and bool(models))

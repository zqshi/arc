"""LLM provider schemas (v6.20 L6) — 多厂商凭证 CRUD + 探活。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LLMProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    kind: Literal["openai_compatible", "anthropic"]
    base_url: str = Field(default="", max_length=500)
    api_key: str = Field(..., min_length=1)
    is_default: bool = False


class LLMProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    # api_key 留空 = 不修改; 非空 = 更新
    api_key: str | None = None
    is_default: bool | None = None


class LLMProviderResponse(BaseModel):
    """GET 响应 — api_key 只返 set 状态, 不回明文 (同 settings 路由模式)。"""

    id: str
    name: str
    kind: str
    base_url: str
    models: list[str]
    is_default: bool
    api_key_set: bool


class VerifyRequest(BaseModel):
    """探活请求 — 验前端临时 (未保存) 凭证, kind+base_url+api_key。"""

    kind: Literal["openai_compatible", "anthropic"]
    base_url: str = ""
    api_key: str = Field(..., min_length=1)
    name: str | None = None  # 仅记录用, 不影响探活


class VerifyResponse(BaseModel):
    valid: bool
    models: list[str] = []
    error_kind: str = ""  # invalid_key | http_error | network | unknown | ""
    error_message: str = ""


class ListModelsResponse(BaseModel):
    models: list[str]
    cached: bool  # 是否命中缓存 (未重新拉取)


class ProviderTemplateResponse(BaseModel):
    """预置模板 (单一真相源, 供前端"添加厂商"选模板)。"""

    key: str
    label: str
    kind: str
    default_base_url: str
    supports_list_models: bool
    suggested_models: list[str]

"""模板 API schema (v5.7.0 T9)。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TemplateResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str = "custom"
    source_project_id: str | None = None
    source_version_id: str | None = None
    source_user_id: str
    schema_template: dict = Field(default_factory=dict)
    entity_patterns: list[str] = Field(default_factory=list)
    state_machine_patterns: list[str] = Field(default_factory=list)
    permission_patterns: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    status: str = "draft"
    scope: str = "personal"
    usage_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    confidence: float = 0.8
    created_at: str | None = None
    last_used_at: str | None = None


class TemplateUpdateRequest(BaseModel):
    """用户编辑模板 (仅 draft 状态可编辑元信息)。"""
    title: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class TemplateSearchRequest(BaseModel):
    query: str
    limit: int = 5


class TemplateApplyRequest(BaseModel):
    """选中模板 apply 到新项目 Supabase。"""
    template_id: str
    project_id: str
    requirement: str
    model_version: int = 1
    supabase_url: str = ""

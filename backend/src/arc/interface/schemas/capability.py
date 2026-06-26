"""能力管理 API schema (v6.8.0 W1)。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CapabilityCreateRequest(BaseModel):
    """创建能力声明 (agent/skill/mcp)。"""

    name: str = Field(..., min_length=1, max_length=100)
    type: str  # agent|skill|mcp (mcp 预留, loader 本期不实现)
    config: dict = Field(default_factory=dict)
    status: str = "active"
    scope: str = "global"


class CapabilityUpdateRequest(BaseModel):
    """更新能力声明 (部分字段, type 不可改)。"""

    name: str | None = None
    config: dict | None = None
    status: str | None = None
    scope: str | None = None


class CapabilityResponse(BaseModel):
    id: str
    name: str
    type: str
    config: dict = Field(default_factory=dict)
    status: str
    scope: str

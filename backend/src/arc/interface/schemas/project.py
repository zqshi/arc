from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tech_stack: str = ""
    repo_url: str = ""
    local_path: str = ""
    conventions: str = ""
    process_constraint: str = "free"
    project_type: Literal["static_site", "binary_app"] = "static_site"
    # v6.19: BINARY_APP 构建目标 (web/capacitor_apk/原生三平台需显式选; tauri_linux 默认)。
    # tauri_windows/capacitor_ios/harmony_hap 走 CI 编排 (原生 OS runner)。
    build_target: Literal[
        "tauri_linux", "web", "capacitor_apk",
        "tauri_windows", "capacitor_ios", "harmony_hap",
    ] | None = None
    # 工作区策略
    workspace_type: Literal["local", "github", "temporary"] = "temporary"
    github_token: str = ""  # workspace_type=github 时可选传入


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    repo_url: str | None = None
    local_path: str | None = None
    conventions: str | None = None
    process_constraint: str | None = None
    project_type: str | None = None
    process_config: dict | None = None
    pipeline_config: dict | None = None
    conversation_config: dict | None = None
    # v6.20 L5: 项目级 LLM 凭证指针 (str(uuid) | None 取消覆盖)
    llm_provider_id: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    tech_stack: str
    repo_url: str
    local_path: str
    conventions: str
    charter: dict | None = None
    codebase_summary: str
    scan_fingerprint: str = ""
    scan_status: str = "idle"
    scan_progress: str = ""
    scan_error: str = ""
    status: str
    process_constraint: str = "free"
    project_type: str = "static_site"
    process_config: dict | None = None
    pipeline_config: dict | None = None
    conversation_config: dict | None = None
    llm_provider_id: str | None = None  # v6.20 L5: 项目级 LLM 凭证指针
    github_connected: bool = False
    github_repo: str | None = None
    created_at: str
    updated_at: str


class VersionCreate(BaseModel):
    name: str | None = Field(None, max_length=100)
    goal: str = ""
    parent_version_id: str | None = None
    version_type: str = Field("minor", pattern=r"^(major|minor|patch)$")


class VersionUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None


class VersionResponse(BaseModel):
    id: str
    project_id: str
    name: str
    goal: str
    status: str
    parent_version_id: str | None = None
    order: int = 0
    changelog: str = ""
    prototype_preview_url: str = ""
    todo_stats: dict[str, int] | None = None
    has_analysis: bool = False
    analysis_stale: bool = False
    created_at: str
    updated_at: str


class PlanningConstraintsRequest(BaseModel):
    team_capacity: int = 3
    iteration_weeks: int = 2
    hard_deadlines: list[str] = Field(default_factory=list)
    release_strategy: str = "mvp"
    priority_framework: str = ""


class PlanningSessionCreate(BaseModel):
    document_ids: list[str] = Field(default_factory=list)
    constraints: PlanningConstraintsRequest | None = None
    version_id: str | None = None


class PlanningSessionResponse(BaseModel):
    id: str
    project_id: str
    version_id: str | None = None
    document_ids: list[str]
    constraints: dict
    roadmap: dict
    conversation_id: str | None = None
    status: str
    created_at: str
    updated_at: str


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    content_type: str
    size: int
    status: str
    parsed_features: list[dict] | None = None
    created_at: str


class ApplyWithDiffRequest(BaseModel):
    abandon_todo_ids: list[str] = Field(default_factory=list)


class DeliverableTrackerResponse(BaseModel):
    todo_id: str
    required: list[str]
    deliverables: dict[str, str]
    completion_pct: float
    is_complete: bool


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = Field("member", pattern=r"^(admin|member|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|member|viewer)$")


class MemberResponse(BaseModel):
    user_id: str
    display_name: str
    username: str | None = None
    role: str
    joined_at: str


# ── Credentials (T2) — 签名/分发凭证配置 ──────────────────────
# creds 不强校验具体字段: 读取侧 load_*_creds_for_project 已对缺失字段容错。
# platform/channel 合法性由 route 路径参数 (SignerType/DistributorType 枚举) 校验。


class SigningCredsUpdate(BaseModel):
    creds: dict


class DistributionCredsUpdate(BaseModel):
    creds: dict


class CredentialsStatusResponse(BaseModel):
    signing: dict[str, bool]
    distribution: dict[str, bool]


class PhaseCapabilitiesUpdate(BaseModel):
    """更新某环节启用能力 (v6.8.0 W3)。"""

    phase: str
    capability_ids: list[uuid.UUID] = Field(default_factory=list)


class BuildTargetReadinessResponse(BaseModel):
    """构建目标就绪状态 (v6.19 T11 方案3) — 前端透出/灰显依据。

    target 为 BuildTarget 字符串值; ready=False 时 reason 说明阻塞原因
    (前端灰显目标并标注, 避免用户选了必失败的目标)。
    verified: 探活结果 (null=未探活/过期乐观判ready, true=探活通过, false=探活失败blocked)。
    """

    target: str
    ready: bool
    reason: str = ""
    verified: bool | None = None


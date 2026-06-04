from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tech_stack: str = ""
    repo_url: str = ""
    local_path: str = ""
    conventions: str = ""
    execution_mode: str = "pipeline"  # deprecated, kept for compat
    process_constraint: str = "free"
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
    execution_mode: str | None = None  # deprecated
    process_constraint: str | None = None
    process_config: dict | None = None
    pipeline_config: dict | None = None
    conversation_config: dict | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    tech_stack: str
    repo_url: str
    local_path: str
    conventions: str
    codebase_summary: str
    scan_fingerprint: str = ""
    scan_status: str = "idle"
    scan_progress: str = ""
    scan_error: str = ""
    status: str
    execution_mode: str  # deprecated
    process_constraint: str = "free"
    process_config: dict | None = None
    pipeline_config: dict | None = None
    conversation_config: dict | None = None
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

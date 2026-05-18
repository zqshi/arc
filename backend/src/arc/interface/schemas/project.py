from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tech_stack: str = ""
    repo_url: str = ""
    conventions: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    repo_url: str | None = None
    conventions: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    tech_stack: str
    repo_url: str
    conventions: str
    status: str
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
    todo_stats: dict[str, int] | None = None
    created_at: str
    updated_at: str

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .todo import TagSchema


class ExperienceResponse(BaseModel):
    id: str
    todo_id: str | None = None
    project_id: str | None = None
    title: str
    scope: str = "project"
    status: str = "draft"
    problem: str
    solution: str
    decisions: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    applicable_scenarios: str | None = None
    tags: list[TagSchema] = Field(default_factory=list)
    confidence: float = 0.0
    reuse_count: int = 0
    metadata: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperienceListResponse(BaseModel):
    items: list[ExperienceResponse]
    total: int
    page: int = 1
    page_size: int = 50


class CreateExperienceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    scope: str = "project"
    problem: str = ""
    solution: str = ""
    decisions: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    applicable_scenarios: str | None = None
    tags: list[TagSchema] = Field(default_factory=list)


class UpdateExperienceRequest(BaseModel):
    title: str | None = None
    problem: str | None = None
    solution: str | None = None
    decisions: list[str] | None = None
    pitfalls: list[str] | None = None
    applicable_scenarios: str | None = None
    scope: str | None = None


class ExperienceFeedbackRequest(BaseModel):
    helpful: bool
    todo_id: str

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .todo import TagSchema


class ExperienceResponse(BaseModel):
    id: str
    todo_id: str | None = None
    title: str
    scope: str = "todo"
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


class CreateExperienceRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    scope: str = "todo"
    problem: str = ""
    solution: str = ""
    decisions: list[str] = Field(default_factory=list)
    pitfalls: list[str] = Field(default_factory=list)
    applicable_scenarios: str | None = None
    tags: list[TagSchema] = Field(default_factory=list)

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TagSchema(BaseModel):
    label: str
    color: str


class CreateTodoRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    project_id: str | None = None
    version_id: str | None = None
    priority: int = Field(2, ge=0, le=3)
    tags: list[TagSchema] = Field(default_factory=list)


class UpdateTodoRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    project_id: str | None = None
    version_id: str | None = None
    priority: int | None = Field(None, ge=0, le=3)
    tags: list[TagSchema] | None = None


class TodoResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    project_id: str | None = None
    version_id: str | None = None
    project_name: str | None = None
    version_name: str | None = None
    priority: int = 2
    current_phase: str | None = None
    tags: list[TagSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    items: list[TodoResponse]
    total: int

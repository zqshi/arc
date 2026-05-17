from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TagSchema(BaseModel):
    label: str
    color: str


class CreateTodoRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""
    tags: list[TagSchema] = Field(default_factory=list)


class UpdateTodoRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    tags: list[TagSchema] | None = None


class TodoResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    current_phase: str | None = None
    tags: list[TagSchema]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TodoListResponse(BaseModel):
    items: list[TodoResponse]
    total: int

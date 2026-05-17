from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExecuteAgentRequest(BaseModel):
    agent_type: str | None = None


class AgentSessionResponse(BaseModel):
    id: str
    todo_id: str
    phase_id: str
    agent_type: str
    external_session_id: str | None = None
    status: str
    task_context: dict[str, Any]
    result_summary: dict[str, Any]
    error_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentTypeInfo(BaseModel):
    value: str
    label: str


class AvailableAgentsResponse(BaseModel):
    agents: list[AgentTypeInfo]
    default: str

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.domain.agent.value_objects import AGENT_LABELS, AgentType
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.agent import (
    AgentSessionResponse,
    AgentTypeInfo,
    AvailableAgentsResponse,
    ExecuteAgentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/{todo_id}/phases/{phase_type}/execute",
    response_model=AgentSessionResponse,
)
async def execute_agent(
    todo_id: str,
    phase_type: str,
    req: ExecuteAgentRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Trigger coding agent execution for a phase."""
    from arc.application.pipeline.service import PipelineService
    from arc.domain.pipeline.value_objects import PhaseType

    try:
        pt = PhaseType(phase_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase type: {phase_type}")

    agent_type = None
    if req.agent_type:
        try:
            agent_type = AgentType(req.agent_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid agent type: {req.agent_type}")

    svc = PipelineService(db)
    try:
        session = await svc.execute_with_agent(UUID(todo_id), pt, agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _session_response(session)


@router.get(
    "/{todo_id}/phases/{phase_type}/agent-session",
    response_model=AgentSessionResponse | None,
)
async def get_agent_session(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Get the agent session for a phase."""
    from arc.application.pipeline.service import PipelineService
    from arc.domain.pipeline.value_objects import PhaseType

    try:
        pt = PhaseType(phase_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase type: {phase_type}")

    svc = PipelineService(db)
    session = await svc.get_agent_session(UUID(todo_id), pt)
    if not session:
        return None
    return _session_response(session)


@router.post(
    "/{todo_id}/phases/{phase_type}/cancel-agent",
    response_model=AgentSessionResponse | None,
)
async def cancel_agent(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Cancel the running agent session for a phase."""
    from arc.application.pipeline.service import PipelineService
    from arc.domain.pipeline.value_objects import PhaseType

    try:
        pt = PhaseType(phase_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase type: {phase_type}")

    svc = PipelineService(db)
    session = await svc.cancel_agent(UUID(todo_id), pt)
    if not session:
        raise HTTPException(status_code=404, detail="No agent session found")
    return _session_response(session)


@router.get(
    "/{todo_id}/phases/{phase_type}/agent-events",
)
async def get_agent_events(todo_id: str, phase_type: str, db: DbSession, user: CurrentUser):
    """Get agent execution events (system messages from phase conversation)."""
    from arc.domain.pipeline.value_objects import PhaseType
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository

    try:
        pt = PhaseType(phase_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase type: {phase_type}")

    phase_repo = PipelinePhaseRepository(db)
    phase = await phase_repo.get_by_todo_and_type(UUID(todo_id), pt)
    if not phase or not phase.conversation_id:
        return []

    conv_repo = ConversationRepository(db)
    conv = await conv_repo.get_by_id(phase.conversation_id)
    if not conv:
        return []

    return [
        {
            "id": str(msg.id),
            "content": msg.content,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            "metadata": msg.metadata or {},
        }
        for msg in conv.messages
        if msg.role.value == "system"
        and msg.metadata
        and ("agent_event_id" in msg.metadata or "agent_type" in msg.metadata)
    ]


@router.get("/agent-types", response_model=AvailableAgentsResponse)
async def list_agent_types(user: CurrentUser):
    """List available coding agent types."""
    from arc.application.agent.registry import agent_registry
    from arc.config import settings

    available = agent_registry.available_agents()
    return AvailableAgentsResponse(
        agents=[AgentTypeInfo(value=a.value, label=AGENT_LABELS[a]) for a in available],
        default=settings.agent_default,
    )


def _session_response(session) -> AgentSessionResponse:
    return AgentSessionResponse(
        id=str(session.id),
        todo_id=str(session.todo_id),
        phase_id=str(session.phase_id),
        agent_type=session.agent_type.value,
        external_session_id=session.external_session_id,
        status=session.status.value,
        task_context=session.task_context or {},
        result_summary=session.result_summary or {},
        error_reason=session.error_reason,
        started_at=session.started_at,
        completed_at=session.completed_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )

"""WebSocket helper functions — auth, heartbeat, sandbox bridge, org lookup."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 60
TOKEN_CHECK_INTERVAL = 120

# ---------------------------------------------------------------------------
# Sandbox approval bridge
# ---------------------------------------------------------------------------
_active_sandboxes: dict[str, object] = {}


def register_sandbox_runtime(conversation_id: str, runtime: object) -> None:
    """Register a sandbox runtime to receive approval responses."""
    _active_sandboxes[conversation_id] = runtime


def unregister_sandbox_runtime(conversation_id: str) -> None:
    """Remove sandbox runtime registration."""
    _active_sandboxes.pop(conversation_id, None)


def _resolve_approval(conversation_id: str, request_id: str, approved: bool) -> None:
    """Forward an approval response to the sandbox runtime."""
    runtime = _active_sandboxes.get(conversation_id)
    if runtime and hasattr(runtime, "respond"):
        runtime.respond(request_id, approved)
    else:
        logger.warning(
            "Approval response for unknown sandbox: conv=%s req=%s",
            conversation_id, request_id,
        )


async def _authenticate_ws(token: str | None):
    if not token:
        return None
    try:
        from arc.application.auth.jwt import verify_access_token
        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.user import UserRepository

        payload = verify_access_token(token)
        async with async_session_factory() as db:
            user = await UserRepository(db).get_by_id(UUID(payload["sub"]))
            if user and user.is_active:
                return user
    except Exception as exc:
        logger.warning("WebSocket auth failed: %s", exc)
    return None


async def _get_org_id_for_todo(db, todo_id: UUID) -> UUID | None:
    from sqlalchemy import select

    from arc.infrastructure.models.project import ProjectModel
    from arc.infrastructure.models.todo import Todo as TodoModel

    result = await db.execute(
        select(ProjectModel.organization_id)
        .join(TodoModel, TodoModel.project_id == ProjectModel.id)
        .where(TodoModel.id == todo_id)
    )
    return result.scalar_one_or_none()


async def _heartbeat(ws, cancel_event: asyncio.Event, token: str | None = None):
    ticks = 0
    try:
        while not cancel_event.is_set():
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            if cancel_event.is_set():
                break
            ticks += HEARTBEAT_INTERVAL
            try:
                await ws.send_json({"type": "ping"})
            except Exception:
                break
            if token and ticks >= TOKEN_CHECK_INTERVAL:
                ticks = 0
                try:
                    from arc.application.auth.jwt import verify_access_token

                    verify_access_token(token)
                except Exception:
                    await ws.send_json({"type": "token_expired"})
                    await ws.close(code=4002, reason="Token expired")
                    break
    except asyncio.CancelledError:
        pass

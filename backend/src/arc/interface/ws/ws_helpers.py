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
# 注 (v6.7): _active_sandboxes 是进程内 dict, 多 worker 下跨进程不可共享。
# 当前沙箱审批为半成品 (execution_engine 的 emit_callback=no-op, runtime
# 未 register_sandbox_runtime), 此路径生产未触发, 暂不引入 bus 改造。
# 未来接线审批功能时, 需将 respond 改为 bus 广播 (arc:sandbox:{cid}),
# 各 worker 的 runtime 监听本地解析 future (future 不可跨进程)。
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

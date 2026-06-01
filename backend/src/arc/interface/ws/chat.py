from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from arc.domain.todo.value_objects import MessageRole
from arc.interface.ws.connection_manager import ConnectionManager, manager
from arc.interface.ws.stream_generator import _build_stream_generator
from arc.interface.ws.ws_helpers import (
    _authenticate_ws,
    _get_org_id_for_todo,
    _heartbeat,
    _resolve_approval,
    register_sandbox_runtime,
    unregister_sandbox_runtime,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Re-export for backward compatibility
__all__ = [
    "router",
    "manager",
    "ConnectionManager",
    "register_sandbox_runtime",
    "unregister_sandbox_runtime",
]


async def _stream_ai_response(
    manager: ConnectionManager,
    conversation_id: str,
    svc,
    conv,
):
    """启动或恢复流式 AI 回复，通过 StreamManager 解耦。

    - 首次调用: 启动后台 Task + subscribe
    - WS 断开后重连: subscribe 到已有 session（自动 replay）
    - WS 断开不影响后台生成和持久化
    """
    from arc.application.execution.stream_manager import stream_manager

    session = stream_manager.get_session(conversation_id)

    if session and not session.done:
        logger.info("Resuming stream for conversation %s", conversation_id)
    else:
        use_autopilot = False
        if hasattr(svc, "get_autonomy") and conv.todo_id:
            try:
                autonomy = await svc.get_autonomy(conv.todo_id)
                use_autopilot = autonomy == "full"
            except Exception:
                pass

        gen = _build_stream_generator(svc, conv, use_autopilot)
        session = stream_manager.start_stream(conversation_id, gen)

    async for event in stream_manager.subscribe(session):
        await manager.broadcast(conversation_id, event)


async def _try_resume_stream(
    manager: ConnectionManager,
    conversation_id: str,
    ws: WebSocket,
) -> bool:
    """检查是否有活跃的 stream session，如果有则恢复。返回是否恢复。"""
    from arc.application.execution.stream_manager import stream_manager

    session = stream_manager.get_session(conversation_id)
    if not session:
        return False

    if session.done:
        return False

    await ws.send_json({
        "type": "stream_resume",
        "message_id": session.message_id,
        "buffered_content": session.full_content,
    })

    async for event in stream_manager.subscribe(session):
        await manager.broadcast(conversation_id, event)

    return True


@router.websocket("/conversations/{conversation_id}")
async def conversation_ws(
    ws: WebSocket,
    conversation_id: str,
    token: str = Query(None),
):
    user = await _authenticate_ws(token)
    if not user:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(conversation_id, ws)

    cancel_heartbeat = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(ws, cancel_heartbeat, token))

    try:
        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.conversation import ConversationRepository

        async with async_session_factory() as db:
            repo = ConversationRepository(db)
            conv = await repo.get_by_id(UUID(conversation_id))
            if not conv:
                await ws.send_json({"type": "error", "detail": "Conversation not found"})
                await ws.close()
                return

            from arc.infrastructure.repositories.todo import TodoRepository
            todo_repo = TodoRepository(db)
            todo = await todo_repo.get_by_id(conv.todo_id, user_id=user.id)
            if not todo:
                await ws.send_json({"type": "error", "detail": "Access denied"})
                await ws.close()
                return

            for msg in conv.messages:
                await ws.send_json(
                    {
                        "type": "message",
                        "message": {
                            "id": str(msg.id),
                            "conversation_id": str(msg.conversation_id),
                            "role": msg.role.value,
                            "content": msg.content,
                            "metadata": msg.metadata,
                            "created_at": msg.created_at.isoformat(),
                        },
                    }
                )

        resume_task = asyncio.create_task(
            _try_resume_stream(manager, conversation_id, ws)
        )

        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            if data.get("type") == "pong":
                continue

            if data.get("type") == "approval_response":
                request_id = data.get("request_id", "")
                approved = bool(data.get("approved", False))
                _resolve_approval(conversation_id, request_id, approved)
                continue

            if data.get("type") == "retry":
                async with async_session_factory() as db:
                    repo = ConversationRepository(db)
                    conv = await repo.get_by_id(UUID(conversation_id))
                    if not conv:
                        await ws.send_json({"type": "error", "detail": "Conversation lost"})
                        continue

                    if conv.purpose.value == "unified":
                        from arc.application.execution.conversation_strategy import (
                            ConversationExecutionService,
                        )

                        svc = ConversationExecutionService(db)
                    else:
                        from arc.application.conversation.service import ConversationService

                        svc = ConversationService(db)
                    await _stream_ai_response(manager, conversation_id, svc, conv)
                continue

            if data.get("type") != "message":
                continue

            content = data.get("content", "").strip()
            if not content:
                continue

            async with async_session_factory() as db:
                repo = ConversationRepository(db)
                conv = await repo.get_by_id(UUID(conversation_id))
                if not conv:
                    await ws.send_json({"type": "error", "detail": "Conversation lost"})
                    continue

                user_msg = conv.add_message(role=MessageRole.USER, content=content)
                await repo.add_message(conv.id, user_msg)
                await db.commit()

                await manager.broadcast(
                    conversation_id,
                    {
                        "type": "message",
                        "message": {
                            "id": str(user_msg.id),
                            "conversation_id": str(user_msg.conversation_id),
                            "role": "user",
                            "content": user_msg.content,
                            "created_at": user_msg.created_at.isoformat(),
                        },
                    },
                )

                org_id = await _get_org_id_for_todo(db, conv.todo_id)
                if org_id:
                    from arc.application.billing.quota_service import QuotaService
                    try:
                        await QuotaService(db).check_ai_call_limit(org_id)
                    except Exception as quota_err:
                        await ws.send_json({"type": "quota_exceeded", "detail": str(quota_err)})
                        await db.commit()
                        continue

                if conv.purpose.value == "unified":
                    from arc.application.execution.conversation_strategy import (
                        ConversationExecutionService,
                    )

                    svc = ConversationExecutionService(db)
                else:
                    from arc.application.conversation.service import ConversationService

                    svc = ConversationService(db)
                await _stream_ai_response(manager, conversation_id, svc, conv)

                if org_id:
                    from arc.application.billing.quota_service import QuotaService
                    await QuotaService(db).increment_ai_calls(org_id)

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected for conversation %s", conversation_id)
    except Exception as exc:
        logger.exception("WebSocket error for conversation %s: %s", conversation_id, exc)
        try:
            await ws.send_json({"type": "error", "detail": "内部错误"})
        except Exception:
            pass
    finally:
        cancel_heartbeat.set()
        heartbeat_task.cancel()
        if 'resume_task' in dir() and not resume_task.done():
            resume_task.cancel()
        await manager.disconnect(conversation_id, ws)

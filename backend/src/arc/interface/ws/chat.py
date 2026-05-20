from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from arc.domain.todo.value_objects import MessageRole

logger = logging.getLogger(__name__)

router = APIRouter()

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 60
TOKEN_CHECK_INTERVAL = 120


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.setdefault(conversation_id, []).append(ws)

    async def disconnect(self, conversation_id: str, ws: WebSocket):
        async with self._lock:
            conns = self.active.get(conversation_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self.active.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, data: dict):
        dead: list[WebSocket] = []
        async with self._lock:
            conns = list(self.active.get(conversation_id, []))
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(conversation_id, ws)


manager = ConnectionManager()


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
    except Exception:
        pass
    return None


async def _stream_ai_response(
    manager: ConnectionManager,
    conversation_id: str,
    svc,
    conv,
):
    ai_msg_id = None
    try:
        async for chunk in svc.generate_response_stream(conv):
            event_type = chunk.get("event")
            if event_type == "artifacts_extracted":
                await manager.broadcast(conversation_id, {
                    "type": "artifacts_extracted",
                    "artifacts": chunk.get("artifacts", []),
                    "artifact_names": chunk.get("artifact_names", []),
                })
                continue

            if ai_msg_id is None:
                ai_msg_id = chunk.get("message_id")
                await manager.broadcast(conversation_id, {
                    "type": "stream_start",
                    "message_id": ai_msg_id,
                })

            await manager.broadcast(conversation_id, {
                "type": "stream_chunk",
                "message_id": ai_msg_id,
                "content": chunk.get("content", ""),
            })
    except Exception as exc:
        logger.error("AI response generation failed: %s", exc, exc_info=True)
        error_msg = "AI响应生成失败"
        from arc.application.ai.resilience import CircuitOpenError
        if isinstance(exc, CircuitOpenError):
            error_msg = "AI服务暂时不可用，请稍后重试"
        await manager.broadcast(conversation_id, {
            "type": "error",
            "detail": error_msg,
        })

    if ai_msg_id:
        await manager.broadcast(conversation_id, {
            "type": "stream_end",
            "message_id": ai_msg_id,
        })


async def _heartbeat(ws: WebSocket, cancel_event: asyncio.Event, token: str | None = None):
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

            for msg in conv.messages:
                await ws.send_json({
                    "type": "message",
                    "message": {
                        "id": str(msg.id),
                        "conversation_id": str(msg.conversation_id),
                        "role": msg.role.value,
                        "content": msg.content,
                        "metadata": msg.metadata,
                        "created_at": msg.created_at.isoformat(),
                    },
                })

        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            if data.get("type") == "pong":
                continue

            if data.get("type") == "retry":
                async with async_session_factory() as db:
                    repo = ConversationRepository(db)
                    conv = await repo.get_by_id(UUID(conversation_id))
                    if not conv:
                        await ws.send_json({"type": "error", "detail": "Conversation lost"})
                        continue

                    if conv.purpose.value == "unified":
                        from arc.application.execution.conversation_strategy import ConversationExecutionService
                        svc = ConversationExecutionService(db)
                    else:
                        from arc.application.conversation.service import ConversationService
                        svc = ConversationService(db)
                    await _stream_ai_response(manager, conversation_id, svc, conv)
                    await db.commit()
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

                await manager.broadcast(conversation_id, {
                    "type": "message",
                    "message": {
                        "id": str(user_msg.id),
                        "conversation_id": str(user_msg.conversation_id),
                        "role": "user",
                        "content": user_msg.content,
                        "created_at": user_msg.created_at.isoformat(),
                    },
                })

                if conv.purpose.value == "unified":
                    from arc.application.execution.conversation_strategy import ConversationExecutionService
                    svc = ConversationExecutionService(db)
                else:
                    from arc.application.conversation.service import ConversationService
                    svc = ConversationService(db)
                await _stream_ai_response(manager, conversation_id, svc, conv)
                await db.commit()

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
        await manager.disconnect(conversation_id, ws)

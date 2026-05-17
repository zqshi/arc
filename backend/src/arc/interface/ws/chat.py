from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from arc.domain.todo.value_objects import MessageRole
from arc.infrastructure.database import async_session_factory
from arc.infrastructure.repositories.conversation import ConversationRepository

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, conversation_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(conversation_id, []).append(ws)

    def disconnect(self, conversation_id: str, ws: WebSocket):
        conns = self.active.get(conversation_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.active.pop(conversation_id, None)

    async def broadcast(self, conversation_id: str, data: dict):
        dead: list[WebSocket] = []
        for ws in self.active.get(conversation_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(conversation_id, ws)


manager = ConnectionManager()


@router.websocket("/conversations/{conversation_id}")
async def conversation_ws(ws: WebSocket, conversation_id: str):
    await manager.connect(conversation_id, ws)
    try:
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

            if data.get("type") == "retry":
                async with async_session_factory() as db:
                    repo = ConversationRepository(db)
                    conv = await repo.get_by_id(UUID(conversation_id))
                    if not conv:
                        await ws.send_json({"type": "error", "detail": "Conversation lost"})
                        continue

                    from arc.application.conversation.service import ConversationService
                    svc = ConversationService(db)

                    ai_msg_id = None
                    try:
                        async for chunk in svc.generate_response_stream(conv):
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
                        logger.error("AI retry failed: %s", exc, exc_info=True)
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

                from arc.application.conversation.service import ConversationService
                svc = ConversationService(db)

                ai_msg_id = None
                try:
                    async for chunk in svc.generate_response_stream(conv):
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
        manager.disconnect(conversation_id, ws)

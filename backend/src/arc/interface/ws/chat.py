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

# ---------------------------------------------------------------------------
# Sandbox approval bridge
# ---------------------------------------------------------------------------
# Maps conversation_id → sandbox runtime for approval resolution.
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


async def _mark_todo_complete(todo_id: UUID) -> None:
    from arc.infrastructure.database import async_session_factory
    from arc.infrastructure.repositories.project import ProjectRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    try:
        async with async_session_factory() as db:
            todo_repo = TodoRepository(db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo or todo.status.value == "done":
                return
            todo.complete()
            await todo_repo.update(todo)

            if todo.github_issue_number and todo.project_id:
                proj_repo = ProjectRepository(db)
                project = await proj_repo.get_by_id(todo.project_id)
                if project and project.github_token:
                    from arc.application.integration.github_service import GitHubService
                    svc = GitHubService(db)
                    await svc.notify_issue_complete(todo, project)

            await db.commit()
    except Exception as exc:
        logger.warning("Failed to mark todo %s complete: %s", todo_id, exc)


async def _resolve_project_info(conv) -> tuple[str | None, str | None]:
    """Extract todo_id and project_id from a conversation."""
    todo_id = str(conv.todo_id) if conv.todo_id else None
    project_id = None
    if todo_id:
        try:
            project_id = str(getattr(conv, "_project_id", "")) or None
            if not project_id:
                from arc.infrastructure.database import async_session_factory
                from arc.infrastructure.repositories.todo import TodoRepository

                async with async_session_factory() as _db:
                    _todo = await TodoRepository(_db).get_by_id(UUID(todo_id))
                    if _todo and _todo.project_id:
                        project_id = str(_todo.project_id)
        except Exception:
            pass
    return todo_id, project_id


def _build_stream_generator(svc, conv, use_autopilot: bool):
    """Build the async generator that yields stream events.

    Wraps the raw svc stream to normalize events into a format suitable
    for both StreamManager buffering and WebSocket broadcast.
    """
    from arc.application.project.task_stream import project_task_stream

    async def _generate():
        todo_id, project_id = await _resolve_project_info(conv)
        stream = svc.run_autopilot(conv) if use_autopilot else svc.generate_response_stream(conv)

        ai_msg_id = None
        try:
            async for chunk in stream:
                event_type = chunk.get("event")

                if event_type == "tool_call":
                    event = {
                        "type": "tool_call",
                        "message_id": chunk.get("message_id", ""),
                        "tool_name": chunk.get("tool_name", ""),
                        "tool_input": chunk.get("tool_input", {}),
                        "round": chunk.get("round", 0),
                        "parallel": chunk.get("parallel", False),
                    }
                    yield event
                    if project_id and todo_id:
                        await project_task_stream.emit(
                            project_id,
                            {"event": "task_status", "todo_id": todo_id,
                             "status": "running",
                             "stage": f"调用工具: {chunk.get('tool_name', '')}"},
                        )
                    continue

                if event_type == "tool_result":
                    yield {
                        "type": "tool_result",
                        "message_id": chunk.get("message_id", ""),
                        "tool_name": chunk.get("tool_name", ""),
                        "output_preview": chunk.get("output_preview", ""),
                        "is_error": chunk.get("is_error", False),
                    }
                    continue

                if event_type == "approval_required":
                    yield {
                        "type": "approval_required",
                        "request_id": chunk.get("request_id", ""),
                        "tool_name": chunk.get("tool_name", ""),
                        "tool_input": chunk.get("tool_input", {}),
                    }
                    continue

                if event_type in (
                    "orchestration_start", "worker_start", "worker_complete",
                    "worker_error", "synthesis_start", "orchestration_complete",
                ):
                    yield {"type": event_type, **{k: v for k, v in chunk.items() if k != "event"}}
                    continue

                if event_type == "artifacts_extracted":
                    yield {
                        "type": "artifacts_extracted",
                        "artifacts": chunk.get("artifacts", []),
                        "artifact_names": chunk.get("artifact_names", []),
                    }
                    if project_id and todo_id:
                        await project_task_stream.emit(
                            project_id,
                            {"event": "task_done", "todo_id": todo_id,
                             "artifacts": chunk.get("artifact_names", [])},
                        )
                    continue

                if event_type in ("autopilot_complete", "autopilot_paused"):
                    yield {"type": event_type, "reason": chunk.get("reason", "")}
                    if event_type == "autopilot_complete" and todo_id:
                        await _mark_todo_complete(UUID(todo_id))
                    if project_id and todo_id:
                        status = "done" if event_type == "autopilot_complete" else "idle"
                        await project_task_stream.emit(
                            project_id,
                            {"event": "task_status", "todo_id": todo_id,
                             "status": status, "stage": chunk.get("reason", "")},
                        )
                    continue

                # --- Text content chunk ---
                if ai_msg_id is None:
                    ai_msg_id = chunk.get("message_id")
                    yield {"type": "stream_start", "message_id": ai_msg_id}
                    if project_id and todo_id:
                        await project_task_stream.emit(
                            project_id,
                            {"event": "task_status", "todo_id": todo_id,
                             "status": "running", "stage": "AI 正在生成回复..."},
                        )

                yield {
                    "type": "stream_chunk",
                    "message_id": ai_msg_id,
                    "content": chunk.get("content", ""),
                }
                if project_id and todo_id:
                    await project_task_stream.emit(
                        project_id,
                        {"event": "task_chunk", "todo_id": todo_id,
                         "content": chunk.get("content", "")},
                    )

        except Exception as exc:
            logger.error("AI response generation failed: %s", exc, exc_info=True)
            error_msg = "AI响应生成失败"
            from arc.application.ai.resilience import CircuitOpenError
            if isinstance(exc, CircuitOpenError):
                error_msg = "AI服务暂时不可用，请稍后重试"
            yield {"type": "error", "detail": error_msg}
            if project_id and todo_id:
                await project_task_stream.emit(
                    project_id,
                    {"event": "task_status", "todo_id": todo_id,
                     "status": "error", "stage": error_msg},
                )

        # 持久化 — 无论 WS 是否在线都执行
        await svc.db.commit()

        if ai_msg_id:
            yield {"type": "stream_end", "message_id": ai_msg_id}
            if project_id and todo_id:
                await project_task_stream.emit(
                    project_id,
                    {"event": "task_status", "todo_id": todo_id,
                     "status": "idle", "stage": "等待用户输入"},
                )

    return _generate()


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
        # 已有活跃 stream — subscribe 获取 replay + 实时事件
        logger.info("Resuming stream for conversation %s", conversation_id)
    else:
        # 新建 stream
        use_autopilot = False
        if hasattr(svc, "get_autonomy") and conv.todo_id:
            try:
                autonomy = await svc.get_autonomy(conv.todo_id)
                use_autopilot = autonomy == "full"
            except Exception:
                pass

        gen = _build_stream_generator(svc, conv, use_autopilot)
        session = stream_manager.start_stream(conversation_id, gen)

    # Subscribe 并转发事件到所有 WS 客户端
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
        # Session 已完成但未过期 — 发送缓冲的最终内容
        # 历史消息已持久化到 DB，会通过正常的 conv.messages 加载
        return False

    # 活跃 stream — 发送 resume 信号 + 已缓冲内容
    await ws.send_json({
        "type": "stream_resume",
        "message_id": session.message_id,
        "buffered_content": session.full_content,
    })

    # 继续转发后续事件
    async for event in stream_manager.subscribe(session):
        await manager.broadcast(conversation_id, event)

    return True


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

        # 检查是否有活跃的 stream session 需要恢复
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
                # Bridge to sandbox runtime's pending Future
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
        # 取消 resume task（后台 stream 会继续运行，不受影响）
        if 'resume_task' in dir() and not resume_task.done():
            resume_task.cancel()
        await manager.disconnect(conversation_id, ws)

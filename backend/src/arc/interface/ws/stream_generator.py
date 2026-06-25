"""Stream generator — builds the async generator that normalizes AI events
for WebSocket broadcast."""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


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

            # 补偿: 如果 todo 还是 pending，先推到 active 再完成
            if todo.status.value == "pending":
                todo.start_conversation()
                await todo_repo.update(todo)

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
                    # 工具调用时也发 stream_start，让前端立即进入 streaming 状态
                    if ai_msg_id is None:
                        msg_id = chunk.get("message_id", "")
                        if msg_id:
                            ai_msg_id = msg_id
                        yield {"type": "stream_start", "message_id": ai_msg_id or ""}
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

                if event_type == "tool_error":
                    yield {
                        "type": "tool_error",
                        "message_id": chunk.get("message_id", ""),
                        "detail": chunk.get("detail", "工具执行异常"),
                    }
                    if project_id and todo_id:
                        await project_task_stream.emit(
                            project_id,
                            {"event": "task_status", "todo_id": todo_id,
                             "status": "error",
                             "stage": chunk.get("detail", "工具执行异常")},
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
                        "tracker": chunk.get("tracker"),
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
                chunk_msg_id = chunk.get("message_id")
                if ai_msg_id is None or (chunk_msg_id and chunk_msg_id != ai_msg_id):
                    # 新消息开始（首轮或 autopilot 新一轮）
                    if ai_msg_id is not None:
                        # 结束上一条消息
                        yield {"type": "stream_end", "message_id": ai_msg_id}
                    ai_msg_id = chunk_msg_id
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

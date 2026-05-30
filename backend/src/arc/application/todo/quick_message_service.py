"""Service for handling quick-message AI generation in background.

Extracts the business logic from routes/todo.py send_quick_message endpoint.
Route layer only does parameter validation and fires off the background task.
"""

from __future__ import annotations

import logging
from uuid import UUID

from arc.application.execution.conversation_strategy import ConversationExecutionService
from arc.application.project.task_stream import project_task_stream
from arc.infrastructure.database import async_session_factory
from arc.infrastructure.repositories.conversation import ConversationRepository

logger = logging.getLogger(__name__)


async def run_ai_response(
    *,
    conversation_id: UUID,
    todo_id: str,
    project_id: str | None,
) -> None:
    """Run AI response generation in background.

    Opens its own DB session (detached from the request lifecycle) and streams
    the AI response chunks, emitting project-level task events along the way.
    """
    async with async_session_factory() as db:
        conv_repo = ConversationRepository(db)
        conv = await conv_repo.get_by_id(conversation_id)
        if not conv:
            return

        svc = ConversationExecutionService(db)
        ai_msg_id = None
        try:
            async for chunk in svc.generate_response_stream(conv):
                event_type = chunk.get("event")
                if event_type == "artifacts_extracted":
                    if project_id:
                        await project_task_stream.emit(
                            project_id,
                            {
                                "event": "task_done",
                                "todo_id": todo_id,
                                "artifacts": chunk.get("artifact_names", []),
                            },
                        )
                    continue

                if ai_msg_id is None:
                    ai_msg_id = chunk.get("message_id")
                    if project_id:
                        await project_task_stream.emit(
                            project_id,
                            {
                                "event": "task_status",
                                "todo_id": todo_id,
                                "status": "running",
                                "stage": "AI 正在生成回复...",
                            },
                        )

                if project_id:
                    await project_task_stream.emit(
                        project_id,
                        {
                            "event": "task_chunk",
                            "todo_id": todo_id,
                            "content": chunk.get("content", ""),
                        },
                    )
        except Exception as exc:
            logger.error("quick-message AI failed: %s", exc, exc_info=True)
            if project_id:
                await project_task_stream.emit(
                    project_id,
                    {
                        "event": "task_status",
                        "todo_id": todo_id,
                        "status": "error",
                        "stage": "AI响应生成失败",
                    },
                )
        finally:
            if project_id:
                await project_task_stream.emit(
                    project_id,
                    {
                        "event": "task_status",
                        "todo_id": todo_id,
                        "status": "idle",
                        "stage": "等待用户输入",
                    },
                )
            await db.commit()

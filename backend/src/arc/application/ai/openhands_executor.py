"""OpenHands execution orchestrator.

Manages the lifecycle of an OpenHands coding-agent session: create session,
send task, poll events until completion, and write execution logs back to the
conversation.
"""

from __future__ import annotations

import asyncio
import logging

from arc.application.ai.openhands_client import (
    OpenHandsClient,
    OpenHandsConnectionError,
    OpenHandsError,
    OpenHandsSessionStatus,
    create_openhands_client,
)
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import MessageRole

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_DURATION_SECONDS = 1800  # 30 minutes


class OpenHandsExecutor:
    """Orchestrates an OpenHands coding session for a given todo."""

    def __init__(self, client: OpenHandsClient | None = None) -> None:
        self._client = client

    async def execute(self, todo_id: str) -> None:
        """Full execution lifecycle: create session, send task, poll, write logs.

        Designed to run as a background task with its own DB session.
        """
        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.conversation import ConversationRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        client = self._client or create_openhands_client()
        try:
            async with async_session_factory() as db:
                repo = TodoRepository(db)
                conv_repo = ConversationRepository(db)

                todo = await repo.get_by_id(todo_id)
                if not todo:
                    logger.error("OpenHandsExecutor: todo %s not found", todo_id)
                    return

                conversations = await conv_repo.list_by_todo_id(todo.id)
                dev_conv = next(
                    (c for c in conversations if c.purpose.value == "development"),
                    None,
                )
                if not dev_conv:
                    logger.error("OpenHandsExecutor: no dev conversation for todo %s", todo_id)
                    return

                task_desc = self._build_task(todo)

                try:
                    session = await client.create_session()
                except OpenHandsConnectionError as exc:
                    msg = dev_conv.add_message(
                        role=MessageRole.SYSTEM,
                        content=f"无法连接OpenHands服务: {exc}",
                    )
                    await conv_repo.add_message(dev_conv.id, msg)
                    todo.mark_error(f"OpenHands连接失败: {exc}")
                    await repo.update(todo)
                    await db.commit()
                    return

                await client.send_task(session.session_id, task_desc)

                msg = dev_conv.add_message(
                    role=MessageRole.SYSTEM,
                    content=f"已发送任务到OpenHands (session: {session.session_id})",
                )
                await conv_repo.add_message(dev_conv.id, msg)
                await db.commit()

                last_event_id = ""
                elapsed = 0

                while elapsed < MAX_POLL_DURATION_SECONDS:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    elapsed += POLL_INTERVAL_SECONDS

                    try:
                        status = await client.get_status(session.session_id)
                    except OpenHandsError as exc:
                        logger.warning("Poll status failed: %s", exc)
                        continue

                    try:
                        events = await client.get_events(
                            session.session_id, since_id=last_event_id
                        )
                    except OpenHandsError as exc:
                        logger.warning("Poll events failed: %s", exc)
                        events = []

                    for event in events:
                        last_event_id = event.id
                        if event.content.strip():
                            log_msg = dev_conv.add_message(
                                role=MessageRole.SYSTEM,
                                content=f"[{event.type}] {event.content}",
                                metadata={"openhands_event_id": event.id},
                            )
                            await conv_repo.add_message(dev_conv.id, log_msg)

                    if events:
                        await db.commit()

                    if status in (
                        OpenHandsSessionStatus.COMPLETED,
                        OpenHandsSessionStatus.ERROR,
                    ):
                        final_msg = (
                            "OpenHands执行完成"
                            if status == OpenHandsSessionStatus.COMPLETED
                            else "OpenHands执行出错"
                        )
                        done_msg = dev_conv.add_message(
                            role=MessageRole.SYSTEM, content=final_msg,
                        )
                        await conv_repo.add_message(dev_conv.id, done_msg)
                        await db.commit()
                        logger.info(
                            "OpenHands session %s finished with status %s",
                            session.session_id, status,
                        )
                        return

                timeout_msg = dev_conv.add_message(
                    role=MessageRole.SYSTEM,
                    content="OpenHands执行超时（30分钟），已停止轮询。",
                )
                await conv_repo.add_message(dev_conv.id, timeout_msg)
                await db.commit()

                try:
                    await client.stop_session(session.session_id)
                except OpenHandsError:
                    pass

        except Exception as exc:
            logger.exception("OpenHandsExecutor unexpected error: %s", exc)
        finally:
            if not self._client:
                await client.close()

    @staticmethod
    def _build_task(todo: Todo) -> str:
        parts = [f"# {todo.title}", ""]
        if todo.description:
            parts.append(f"## 描述\n{todo.description}")
        if todo.background:
            parts.append(f"## 背景\n{todo.background}")
        if todo.goals:
            parts.append(f"## 目标\n{todo.goals}")
        if todo.boundaries:
            parts.append(f"## 边界条件\n{todo.boundaries}")
        if todo.acceptance:
            parts.append(f"## 验收标准\n{todo.acceptance}")
        if todo.tech_plan:
            parts.append(f"## 技术方案\n{todo.tech_plan}")
        return "\n\n".join(parts)


async def run_openhands_background(todo_id: str) -> None:
    """Entry point for background task execution."""
    executor = OpenHandsExecutor()
    await executor.execute(todo_id)

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.agent.context_builder import TaskContextBuilder
from arc.application.agent.events import AgentEvent
from arc.application.agent.registry import agent_registry
from arc.domain.agent.entity import AgentSession
from arc.domain.agent.value_objects import AgentType, SessionStatus
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.value_objects import MessageRole
from arc.infrastructure.repositories.agent import AgentSessionRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_DURATION_SECONDS = 1800


class AgentSessionManager:
    """Orchestrates agent session lifecycle: start, poll, writeback, complete."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = AgentSessionRepository(db)
        self.phase_repo = PipelinePhaseRepository(db)
        self.conv_repo = ConversationRepository(db)

    async def start_session(
        self,
        todo_id: uuid.UUID,
        phase_type: PhaseType,
        agent_type: AgentType | None = None,
    ) -> AgentSession:
        """Create an agent session and launch execution in the background."""
        from arc.config import settings

        if agent_type is None:
            phase_agent = getattr(settings, f"agent_{phase_type.value}", "")
            agent_type = AgentType(phase_agent) if phase_agent else AgentType(settings.agent_default)

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise ValueError(f"Phase {phase_type.value} not found for todo {todo_id}")

        existing = await self.session_repo.get_by_phase_id(phase.id)
        if existing and not existing.is_terminal:
            return existing

        context_builder = TaskContextBuilder(self.db)
        context = await context_builder.build(todo_id)

        session = AgentSession(
            todo_id=todo_id,
            phase_id=phase.id,
            agent_type=agent_type,
            task_context=context.to_dict(),
        )
        session = await self.session_repo.create(session)

        phase.agent_session_id = session.id
        await self.phase_repo.update(phase)
        await self.db.commit()

        task = asyncio.create_task(
            self._execute_and_poll(session.id, context),
            name=f"agent-{session.id}",
        )
        task.add_done_callback(self._task_done_callback)
        return session

    @staticmethod
    def _task_done_callback(task: asyncio.Task) -> None:
        if task.cancelled():
            logger.info("Agent task %s was cancelled", task.get_name())
        elif exc := task.exception():
            logger.error("Agent task %s failed unexpectedly: %s", task.get_name(), exc)

    async def cancel_session(self, session_id: uuid.UUID) -> AgentSession:
        session = await self.session_repo.get_by_id(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if session.is_terminal:
            return session

        adapter = agent_registry.create(session.agent_type)
        try:
            if session.external_session_id:
                await adapter.cancel(session.external_session_id)
        except Exception as exc:
            logger.warning("Failed to cancel external session: %s", exc)
        finally:
            await adapter.close()

        session.cancel()
        return await self.session_repo.update(session)

    async def get_session(self, session_id: uuid.UUID) -> AgentSession | None:
        return await self.session_repo.get_by_id(session_id)

    async def get_session_for_phase(self, phase_id: uuid.UUID) -> AgentSession | None:
        return await self.session_repo.get_by_phase_id(phase_id)

    async def _execute_and_poll(self, session_id: uuid.UUID, context) -> None:
        """Background task: start agent, poll events, write back to conversation."""
        from arc.infrastructure.database import async_session_factory

        async with async_session_factory() as db:
            repo = AgentSessionRepository(db)
            conv_repo = ConversationRepository(db)
            phase_repo = PipelinePhaseRepository(db)

            session = await repo.get_by_id(session_id)
            if not session:
                return

            adapter = agent_registry.create(session.agent_type)
            try:
                external_id = await adapter.start(context)
                session.start(external_id)
                await repo.update(session)
                await db.commit()

                await self._write_to_conversation(
                    conv_repo, phase_repo, session,
                    f"已启动 {session.agent_type.value} 执行 (session: {external_id})",
                )
                await db.commit()

                last_event_id = ""
                elapsed = 0

                while elapsed < MAX_POLL_DURATION_SECONDS:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)
                    elapsed += POLL_INTERVAL_SECONDS

                    session = await repo.get_by_id(session_id)
                    if not session or session.is_terminal:
                        return

                    try:
                        status = await adapter.get_status(external_id)
                    except Exception as exc:
                        logger.warning("Agent status poll failed: %s", exc)
                        continue

                    try:
                        events = await adapter.get_events(external_id, since=last_event_id)
                    except Exception as exc:
                        logger.warning("Agent events poll failed: %s", exc)
                        events = []

                    for event in events:
                        last_event_id = event.event_id
                        await self._write_to_conversation(
                            conv_repo, phase_repo, session,
                            f"[{event.event_type.value}] {event.content}",
                            metadata={"agent_event_id": event.event_id},
                        )

                    if events:
                        await db.commit()

                    if status in (SessionStatus.COMPLETED, SessionStatus.ERROR):
                        if status == SessionStatus.COMPLETED:
                            session.complete()
                            await self._write_to_conversation(
                                conv_repo, phase_repo, session,
                                f"{session.agent_type.value} 执行完成",
                            )
                        else:
                            session.mark_error("Agent reported error status")
                            await self._write_to_conversation(
                                conv_repo, phase_repo, session,
                                f"{session.agent_type.value} 执行出错",
                            )
                        await repo.update(session)
                        await db.commit()
                        return

                session.mark_error("执行超时（30分钟）")
                await repo.update(session)
                await self._write_to_conversation(
                    conv_repo, phase_repo, session,
                    f"{session.agent_type.value} 执行超时，已停止",
                )
                await db.commit()

                try:
                    await adapter.cancel(external_id)
                except Exception:
                    pass

            except Exception as exc:
                logger.exception("Agent execution failed: %s", exc)
                session = await repo.get_by_id(session_id)
                if session and not session.is_terminal:
                    session.mark_error(str(exc))
                    await repo.update(session)
                    await self._write_to_conversation(
                        conv_repo, phase_repo, session,
                        f"Agent执行异常: {exc}",
                    )
                    await db.commit()
            finally:
                await adapter.close()

    @staticmethod
    async def _write_to_conversation(
        conv_repo: ConversationRepository,
        phase_repo: PipelinePhaseRepository,
        session: AgentSession,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        phase = await phase_repo.get_by_id(session.phase_id)
        if not phase or not phase.conversation_id:
            return

        conv = await conv_repo.get_by_id(phase.conversation_id)
        if not conv:
            return

        msg = conv.add_message(
            role=MessageRole.SYSTEM,
            content=content,
            metadata=metadata or {"agent_type": session.agent_type.value},
        )
        await conv_repo.add_message(conv.id, msg)

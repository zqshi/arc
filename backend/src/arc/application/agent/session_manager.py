from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.agent.context_builder import TaskContextBuilder
from arc.application.agent.registry import agent_registry
from arc.domain.agent.entity import AgentSession
from arc.domain.agent.value_objects import AgentType, SessionStatus
from arc.domain.errors import NotFoundError
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.project.value_objects import GitSyncConfig
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
            agent_type = (
                AgentType(phase_agent) if phase_agent else AgentType(settings.agent_default)
            )

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise NotFoundError(f"Phase {phase_type.value} not found for todo {todo_id}")

        existing = await self.session_repo.get_by_phase_id(phase.id)
        if existing and not existing.is_terminal:
            return existing

        context_builder = TaskContextBuilder(self.db)
        context = await context_builder.build(todo_id, phase_type.value)

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
            raise NotFoundError(f"Session {session_id} not found")

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
                    conv_repo,
                    phase_repo,
                    session,
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
                            conv_repo,
                            phase_repo,
                            session,
                            f"[{event.event_type.value}] {event.content}",
                            metadata={"agent_event_id": event.event_id},
                        )

                    if events:
                        await db.commit()

                    if status in (SessionStatus.COMPLETED, SessionStatus.ERROR):
                        if status == SessionStatus.COMPLETED:
                            session.complete()
                            await self._write_to_conversation(
                                conv_repo,
                                phase_repo,
                                session,
                                f"{session.agent_type.value} 执行完成",
                            )
                            # Git Sync: 检测代码变更并通知前端
                            await self._check_git_changes(
                                session, context, conv_repo, phase_repo, db
                            )
                        else:
                            session.mark_error("Agent reported error status")
                            await self._write_to_conversation(
                                conv_repo,
                                phase_repo,
                                session,
                                f"{session.agent_type.value} 执行出错",
                            )
                        await repo.update(session)
                        await db.commit()
                        return

                session.mark_error("执行超时（30分钟）")
                await repo.update(session)
                await self._write_to_conversation(
                    conv_repo,
                    phase_repo,
                    session,
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
                        conv_repo,
                        phase_repo,
                        session,
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

    @staticmethod
    async def _check_git_changes(
        session: AgentSession,
        context,
        conv_repo: ConversationRepository,
        phase_repo: PipelinePhaseRepository,
        db: AsyncSession,
    ) -> None:
        """Agent 完成后检测 git 变更，通过 WS 通知前端。"""
        from arc.application.agent.git_sync import GitSync

        project_path = None
        if context.project_context:
            for line in context.project_context.splitlines():
                if line.startswith("工作目录:"):
                    project_path = line.split(":", 1)[1].strip()
                    break

        if not project_path:
            return

        try:
            git = GitSync(project_path)
            changes = await git.detect_changes()
        except Exception as exc:
            logger.warning("Git change detection failed: %s", exc)
            return

        if not changes.has_changes:
            return

        # 检查项目 git_sync 配置 (v6.23 D2: 走类型化 VO 访问器, 替代裸 dict 读)
        from arc.infrastructure.repositories.project import ProjectRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        todo = await TodoRepository(db).get_by_id(session.todo_id)
        git_sync_cfg = GitSyncConfig()
        if todo and todo.project_id:
            project = await ProjectRepository(db).get_by_id(todo.project_id)
            if project:
                git_sync_cfg = project.git_sync_config()

        # auto_commit + auto_push: 直接推送，不等用户确认
        if git_sync_cfg.auto_commit and git_sync_cfg.auto_push:
            commit_msg = f"{git_sync_cfg.commit_prefix}: {todo.title if todo else 'agent changes'}"
            branch = git_sync_cfg.target_branch or None
            result = await git.commit_and_push(commit_msg, branch)
            status_msg = (
                f"代码已自动推送: {result.commit_sha[:7]} → {result.branch}"
                if result.success
                else f"自动推送失败: {result.error}"
            )
            await AgentSessionManager._write_to_conversation(
                conv_repo, phase_repo, session, status_msg,
                metadata={"type": "auto_push_result", "success": result.success},
            )
            return

        # 非自动模式: 通知前端，等待用户确认
        change_summary = (
            f"检测到代码变更: {len(changes.files_changed)} 个文件 "
            f"(+{changes.insertions} -{changes.deletions})"
        )
        await AgentSessionManager._write_to_conversation(
            conv_repo, phase_repo, session, change_summary,
            metadata={
                "type": "code_changes_ready",
                "files_changed": changes.files_changed,
                "insertions": changes.insertions,
                "deletions": changes.deletions,
                "diff_stat": changes.diff_stat,
                "diff_preview": changes.diff_preview[:2000],
            },
        )

        # 通过 project_task_stream 广播给前端
        from arc.application.project.task_stream import project_task_stream

        if todo and todo.project_id:
            await project_task_stream.emit(
                str(todo.project_id),
                {
                    "event": "code_changes_ready",
                    "todo_id": str(session.todo_id),
                    "files_changed": len(changes.files_changed),
                    "insertions": changes.insertions,
                    "deletions": changes.deletions,
                    "diff_stat": changes.diff_stat,
                    "diff_preview": changes.diff_preview[:2000],
                },
            )

        logger.info(
            "Git changes detected for todo %s: %d files (+%d -%d)",
            session.todo_id, len(changes.files_changed),
            changes.insertions, changes.deletions,
        )

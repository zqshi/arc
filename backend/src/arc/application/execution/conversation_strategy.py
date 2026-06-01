"""对话驱动执行模式的核心服务。

职责：对话初始化 + 交付物追踪器管理 + 项目配置读取。
执行编排和 prompt 构建已提取到:
- execution/execution_engine.py — 流式执行编排
- context/prompt_builder.py — 系统提示词组装
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.prompt_builder import PromptBuilder
from arc.application.execution.artifact_extractor import ArtifactExtractor
from arc.application.execution.execution_engine import ExecutionEngine
from arc.domain.conversation.entity import Conversation
from arc.domain.planning.entity import DeliverableTracker
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole, TodoStatus
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.planning import DeliverableTrackerRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


class ConversationExecutionService:
    """对话驱动模式的入口服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.artifact_repo = ArtifactRepository(db)
        self.tracker_repo = DeliverableTrackerRepository(db)
        self.extractor = ArtifactExtractor(db)
        self._prompt_builder = PromptBuilder(db)
        self._engine = ExecutionEngine(
            db, self._prompt_builder, self.conv_repo, self.tracker_repo, self.extractor,
        )

    async def initialize(
        self,
        todo_id: uuid.UUID,
        required_deliverables: list[str] | None = None,
    ) -> tuple[Conversation, DeliverableTracker]:
        """初始化对话模式：创建统一对话 + 交付物追踪器。"""
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        existing_conv = await self.conv_repo.get_by_todo_and_purpose(
            todo_id, ConversationPurpose.UNIFIED,
        )
        if existing_conv:
            if todo.status == TodoStatus.PENDING:
                todo.start_conversation()
                await self.todo_repo.update(todo)
            tracker = await self.tracker_repo.get_by_todo_id(todo_id)
            if not tracker:
                tracker = await self._create_tracker(todo_id, required_deliverables)
            else:
                tracker = await self._sync_tracker_required(
                    tracker, todo, required_deliverables
                )
            return existing_conv, tracker

        conv = Conversation(
            todo_id=todo_id, purpose=ConversationPurpose.UNIFIED,
        )
        conv.add_message(role=MessageRole.SYSTEM, content=f"对话模式启动：{todo.title}")

        greeting = (
            f"你好！我来帮你完成「{todo.title}」。\n\n"
            f"在对话过程中，我会根据我们的讨论自动产出结构化交付物。"
            f"你可以随时在侧边面板查看进度。\n\n"
        )
        if todo.description:
            greeting += f"我看到你的描述是：{todo.description}\n\n"
            greeting += "先聊聊这个需求要解决什么问题？有哪些关键的用户场景？"
        else:
            greeting += "先描述一下你想做什么？解决什么问题？"

        conv.add_message(role=MessageRole.ASSISTANT, content=greeting)
        await self.conv_repo.create(conv)

        if todo.status == TodoStatus.PENDING:
            todo.start_conversation()
            await self.todo_repo.update(todo)

        tracker = await self._create_tracker(todo_id, required_deliverables)
        return conv, tracker

    # ------------------------------------------------------------------
    # Execution delegation
    # ------------------------------------------------------------------

    async def generate_response_stream(
        self, conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """生成 AI 流式回复。委托给 ExecutionEngine。"""
        project_path = await self._get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._is_orchestration_enabled(
            conversation.todo_id
        )

        async for chunk in self._engine.generate_response_stream(
            conversation,
            project_path=project_path,
            sandbox_policy=sandbox_policy,
            orchestration_enabled=orchestration_enabled,
        ):
            yield chunk

    async def run_autopilot(
        self, conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """自驾模式。委托给 ExecutionEngine。"""
        project_path = await self._get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._is_orchestration_enabled(
            conversation.todo_id
        )
        async for chunk in self._engine.run_autopilot(
            conversation,
            project_path=project_path,
            sandbox_policy=sandbox_policy,
            orchestration_enabled=orchestration_enabled,
        ):
            yield chunk

    async def get_autonomy(self, todo_id: uuid.UUID) -> str:
        """获取项目的 agent_autonomy 配置。"""
        return await self._prompt_builder._get_autonomy(
            await self.todo_repo.get_by_id(todo_id)
        )

    async def get_tracker_state(self, todo_id: uuid.UUID) -> dict:
        """获取交付物追踪器状态。"""
        tracker = await self.tracker_repo.get_by_todo_id(todo_id)
        if not tracker:
            return {"required": [], "deliverables": {}, "completion_pct": 0}

        todo = await self.todo_repo.get_by_id(todo_id)
        tracker = await self._sync_tracker_required(tracker, todo, None)

        from arc.domain.planning.value_objects import DeliverableStatus

        artifacts = await self.artifact_repo.list_by_todo_id(todo_id)
        produced_types = {a.artifact_type.value for a in artifacts}
        reconciled = False
        for atype in produced_types:
            status = tracker.deliverables.get(atype)
            if status and status not in (
                DeliverableStatus.PRODUCED, DeliverableStatus.CONFIRMED,
            ):
                tracker.deliverables[atype] = DeliverableStatus.PRODUCED
                reconciled = True
        if reconciled:
            await self.tracker_repo.update(tracker)
            await self.db.commit()

        # 交付物全部完成 → 自动将 todo 状态推进到 done
        if tracker.is_complete and todo and todo.status.value == "active":
            try:
                todo.complete()
                await self.todo_repo.update(todo)
                await self.db.commit()
                logger.info("Auto-completed todo %s: all deliverables done", todo_id)
            except Exception:
                logger.debug("Todo %s auto-complete skipped (status transition invalid)", todo_id)

        return {
            "required": tracker.required,
            "deliverables": {k: v.value for k, v in tracker.deliverables.items()},
            "completion_pct": tracker.completion_pct,
            "is_complete": tracker.is_complete,
        }

    async def _get_project_local_path(self, todo_id: uuid.UUID) -> str | None:
        from pathlib import Path
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.local_path:
            return None
        resolved = Path(project.local_path).expanduser().resolve()
        if resolved.is_dir():
            return str(resolved)
        logger.warning("Project local_path does not exist: %s", project.local_path)
        return None

    async def _get_sandbox_policy(self, todo_id: uuid.UUID):
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return None
        sandbox_cfg = project.conversation_config.get("sandbox")
        if not sandbox_cfg or sandbox_cfg.get("mode", "none") == "none":
            return None
        from arc.domain.sandbox.value_objects import SandboxPolicy

        return SandboxPolicy.from_dict(sandbox_cfg)

    async def _is_orchestration_enabled(self, todo_id: uuid.UUID) -> bool:
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return False
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return False
        orch_cfg = project.conversation_config.get("orchestration", {})
        return bool(orch_cfg.get("enabled", False))

    # ------------------------------------------------------------------
    # Tracker management
    # ------------------------------------------------------------------

    async def _create_tracker(
        self, todo_id: uuid.UUID, required_types: list[str] | None,
    ) -> DeliverableTracker:
        if not required_types:
            from arc.infrastructure.repositories.project import ProjectRepository

            todo = await self.todo_repo.get_by_id(todo_id)
            if todo and todo.project_id:
                project = await ProjectRepository(self.db).get_by_id(todo.project_id)
                if project and project.conversation_config:
                    required_types = project.conversation_config.get(
                        "required_deliverables"
                    )
        if not required_types:
            from arc.domain.project.value_objects import DEFAULT_CONVERSATION_CONFIG

            required_types = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]

        return await self.extractor.get_or_create_tracker(todo_id, required_types)

    async def _sync_tracker_required(
        self, tracker: DeliverableTracker, todo, override: list[str] | None,
    ) -> DeliverableTracker:
        """同步 tracker.required 与当前规范列表。"""
        canonical = override
        if not canonical:
            if todo and todo.project_id:
                from arc.infrastructure.repositories.project import ProjectRepository

                project = await ProjectRepository(self.db).get_by_id(todo.project_id)
                if project and project.conversation_config:
                    canonical = project.conversation_config.get(
                        "required_deliverables"
                    )
        if not canonical:
            from arc.domain.project.value_objects import DEFAULT_CONVERSATION_CONFIG

            canonical = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]

        from arc.domain.planning.value_objects import DeliverableStatus

        existing = set(tracker.required)
        added = [t for t in canonical if t not in existing]
        needs_reorder = tracker.required != [
            t for t in canonical if t in existing
        ] + added

        if not added and not needs_reorder:
            return tracker

        for t in added:
            if t not in tracker.deliverables:
                tracker.deliverables[t] = DeliverableStatus.PENDING

        tracker.required = list(canonical)
        await self.tracker_repo.update(tracker)
        logger.info("Synced tracker %s: added %s", tracker.id, added)
        return tracker

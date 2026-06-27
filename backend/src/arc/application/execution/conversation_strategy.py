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
from arc.application.execution.conversation_context import ConversationContextProvider
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
        # v6.11 T4: 上下文查询与 greeting 抽离到 ConversationContextProvider
        # (组合而非继承, 保持测试 patch 点可平移到 service._context)
        self._context = ConversationContextProvider(db, self.todo_repo)
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

        # 上下文感知 greeting — 基于分析缓存 + todo 来源 + 描述丰富度
        greeting = await self._context.build_context_aware_greeting(todo)

        conv.add_message(role=MessageRole.ASSISTANT, content=greeting)
        await self.conv_repo.create(conv)

        if todo.status == TodoStatus.PENDING:
            todo.start_conversation()
            await self.todo_repo.update(todo)
            # 自动激活版本
            if todo.version_id:
                await self._auto_activate_version(todo.version_id)

        tracker = await self._create_tracker(todo_id, required_deliverables)
        return conv, tracker

    # ------------------------------------------------------------------
    # Execution delegation
    # ------------------------------------------------------------------

    async def generate_response_stream(
        self, conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """生成 AI 流式回复。委托给 ExecutionEngine。"""
        # 补偿性状态推进：对话已在进行，确保 todo 状态为 active
        await self._ensure_todo_active(conversation.todo_id)

        project_path = await self._context.get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._context.get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._context.is_orchestration_enabled(
            conversation.todo_id
        )
        llm_config = await self._context.get_llm_config(conversation.todo_id)

        async for chunk in self._engine.generate_response_stream(
            conversation,
            project_path=project_path,
            sandbox_policy=sandbox_policy,
            orchestration_enabled=orchestration_enabled,
            llm_config=llm_config,
        ):
            yield chunk

    async def run_autopilot(
        self, conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """自驾模式。委托给 ExecutionEngine。"""
        # 补偿性状态推进：自驾模式运行中确保 todo 状态为 active
        await self._ensure_todo_active(conversation.todo_id)

        project_path = await self._context.get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._context.get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._context.is_orchestration_enabled(
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

        # 补偿性状态推进：有 tracker 说明对话已开始，确保状态为 active
        if todo and todo.status == TodoStatus.PENDING:
            try:
                todo.start_conversation()
                await self.todo_repo.update(todo)
                await self.db.commit()
                logger.info("Compensated todo %s status: pending → active", todo_id)
            except Exception:
                logger.debug("Todo %s status compensation skipped", todo_id)

        tracker = await self._sync_tracker_required(tracker, todo, None)

        from arc.domain.planning.value_objects import DeliverableStatus

        artifacts = await self.artifact_repo.list_by_todo_id(todo_id)
        qualified_types = self._qualified_types_from(artifacts)

        # 仅对未完成项目做质量 reconcile (避免历史 done 项目被降级)
        if todo and todo.status.value != "done":
            reconciled = False
            for atype in qualified_types:
                status = tracker.deliverables.get(atype)
                if status and status not in (
                    DeliverableStatus.PRODUCED, DeliverableStatus.CONFIRMED,
                ):
                    tracker.deliverables[atype] = DeliverableStatus.PRODUCED
                    reconciled = True
            # 反向 reconcile: PRODUCED 但未过门禁 → 降级 IN_PROGRESS (修复虚假达标)
            for atype, status in list(tracker.deliverables.items()):
                if status == DeliverableStatus.PRODUCED and atype not in qualified_types:
                    tracker.deliverables[atype] = DeliverableStatus.IN_PROGRESS
                    reconciled = True
            if reconciled:
                await self.tracker_repo.update(tracker)
                await self.db.commit()

        quality_complete = tracker.is_quality_complete(qualified_types)

        # 交付物全部质量达标 → 自动将 todo 状态推进到 done
        if quality_complete and todo and todo.status.value == "active":
            try:
                todo.complete()
                await self.todo_repo.update(todo)
                await self.db.commit()
                logger.info("Auto-completed todo %s: all deliverables quality-qualified", todo_id)
            except Exception:
                logger.debug("Todo %s auto-complete skipped (status transition invalid)", todo_id)

        return {
            "required": tracker.required,
            "deliverables": {k: v.value for k, v in tracker.deliverables.items()},
            "completion_pct": tracker.completion_pct,
            "is_complete": quality_complete,
        }

    @staticmethod
    def _qualified_types_from(artifacts) -> set[str]:
        """从 artifact 列表提取已过质量门禁的类型 (content._quality.passed=True)。"""
        result: set[str] = set()
        for a in artifacts:
            if isinstance(a.content, dict):
                q = a.content.get("_quality")
                if isinstance(q, dict) and q.get("passed") is True:
                    result.add(a.artifact_type.value)
        return result

    async def _ensure_todo_active(self, todo_id: uuid.UUID) -> None:
        """补偿性状态推进：如果 todo 仍为 PENDING，推进到 ACTIVE。

        场景: 对话已在进行但 status 未更新（如 WS 路径跳过 initialize）。
        同时检查关联版本：如果版本还在 planning，自动激活为 active。
        """
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or todo.status != TodoStatus.PENDING:
            return
        try:
            todo.start_conversation()
            await self.todo_repo.update(todo)
            # 自动激活版本：用户开始需求迭代时，版本自动从 planning → active
            if todo.version_id:
                await self._auto_activate_version(todo.version_id)
            await self.db.commit()
            logger.info("Compensated todo %s status: pending → active", todo_id)
        except Exception as exc:
            logger.debug("Todo %s status compensation failed: %s", todo_id, exc)

    async def _auto_activate_version(self, version_id: uuid.UUID) -> None:
        """当版本下有需求开始迭代时，自动将版本从 planning 推进到 active。"""
        from arc.infrastructure.repositories.project import VersionRepository
        version_repo = VersionRepository(self.db)
        version = await version_repo.get_by_id(version_id)
        if not version or version.status.value != "planning":
            return
        try:
            version.activate()
            await version_repo.update(version)
            logger.info("Auto-activated version %s: planning → active", version_id)
        except Exception as exc:
            logger.debug("Version %s auto-activate failed: %s", version_id, exc)

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
                if project:
                    # 优先从项目自定义配置取
                    if project.conversation_config:
                        required_types = project.conversation_config.get(
                            "required_deliverables"
                        )
                    # 没有自定义配置时，按 constraint 级别选择
                    if not required_types:
                        from arc.domain.project.value_objects import DELIVERABLES_BY_CONSTRAINT
                        required_types = DELIVERABLES_BY_CONSTRAINT.get(
                            project.process_constraint.value
                        )
        if not required_types:
            from arc.domain.project.value_objects import FREE_DELIVERABLES
            required_types = FREE_DELIVERABLES

        # v6.9: 按项目类型裁剪可见交付物 — 非app类不显示 app_code/build 节点
        required_types = await self._filter_visible_deliverables(todo_id, required_types)

        return await self.extractor.get_or_create_tracker(todo_id, required_types)

    async def _filter_visible_deliverables(
        self, todo_id: uuid.UUID, deliverables: list[str]
    ) -> list[str]:
        """v6.9: 按项目类型裁剪可见交付物(非app类去 app_code/build)。

        tracker.required 决定前端交付物节点显示, 类型过滤让非app类不显示
        app_code/build 节点(无原生构建产物)。graceful: 取项目失败→原样返回。
        """
        try:
            from arc.domain.project.value_objects import is_deliverable_visible
            from arc.infrastructure.repositories.project import ProjectRepository

            todo = await self.todo_repo.get_by_id(todo_id)
            if not todo or not todo.project_id:
                return deliverables
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if not project:
                return deliverables
            return [
                d
                for d in deliverables
                if is_deliverable_visible(project.project_type, d)
            ]
        except Exception:
            return deliverables

    async def _sync_tracker_required(
        self, tracker: DeliverableTracker, todo, override: list[str] | None,
    ) -> DeliverableTracker:
        """同步 tracker.required 与当前规范列表。"""
        canonical = override
        if not canonical:
            if todo and todo.project_id:
                from arc.infrastructure.repositories.project import ProjectRepository

                project = await ProjectRepository(self.db).get_by_id(todo.project_id)
                if project:
                    if project.conversation_config:
                        canonical = project.conversation_config.get(
                            "required_deliverables"
                        )
                    if not canonical:
                        from arc.domain.project.value_objects import DELIVERABLES_BY_CONSTRAINT
                        canonical = DELIVERABLES_BY_CONSTRAINT.get(
                            project.process_constraint.value
                        )
        if not canonical:
            from arc.domain.project.value_objects import FREE_DELIVERABLES
            canonical = FREE_DELIVERABLES

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

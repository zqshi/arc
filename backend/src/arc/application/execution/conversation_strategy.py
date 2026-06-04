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

        # 上下文感知 greeting — 基于分析缓存 + todo 来源 + 描述丰富度
        greeting = await self._build_context_aware_greeting(todo)

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

        project_path = await self._get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._is_orchestration_enabled(
            conversation.todo_id
        )
        llm_config = await self._get_llm_config(conversation.todo_id)

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
            from arc.domain.project.value_objects import VersionStatus
            version.activate()
            await version_repo.update(version)
            logger.info("Auto-activated version %s: planning → active", version_id)
        except Exception as exc:
            logger.debug("Version %s auto-activate failed: %s", version_id, exc)

    async def _build_context_aware_greeting(self, todo) -> str:
        """基于版本分析缓存 + todo 来源 + 描述丰富度生成上下文感知的开场白。

        不调用 LLM，纯粹基于已有数据动态组装。
        """
        constraint = await self._get_project_constraint(todo)
        parts: list[str] = []

        # 1. 开头 — 表明意图
        parts.append(f"你好！我来帮你完成「{todo.title}」。")

        # 2. 版本分析洞察（如果有缓存 — 展示 AI 对项目状态的理解）
        analysis_insight = await self._get_analysis_insight_for_greeting(todo)
        if analysis_insight:
            parts.append(analysis_insight)

        # 3. 来源感知 — AI建议来源的需求展示理解
        if todo.source_session_id:
            parts.append(
                "这个需求来自版本分析建议，我已了解其背景和优先级定位。"
            )

        # 4. 流程说明 — 基于 constraint 级别
        if constraint == "strict":
            parts.append(
                "我会按标准研发流程逐步推进，每阶段产出结构化交付物，"
                "通过门禁确认后进入下一阶段。右侧面板实时展示进度。"
            )
        elif constraint == "moderate":
            parts.append(
                "我会在对话中自动产出结构化交付物，"
                "你可以随时在右侧面板查看进度和已产出成果。"
            )
        # free 模式不做流程声明 — 自然对话

        # 5. 需求理解 + 引导
        if todo.description:
            desc_preview = todo.description[:300]
            has_rich_context = (
                len(todo.description) > 50
                or todo.description.startswith("[P")
                or bool(todo.source_session_id)
            )
            parts.append(f"需求描述：{desc_preview}")
            if has_rich_context:
                parts.append(
                    "背景信息已足够清晰，我直接开始推进。"
                    "如有需要补充的随时告诉我。"
                )
            else:
                parts.append("先聊聊这个需求要解决什么问题？有哪些关键的用户场景？")
        else:
            parts.append("先描述一下你想做什么？解决什么问题？")

        return "\n\n".join(parts)

    async def _get_analysis_insight_for_greeting(self, todo) -> str:
        """从版本分析缓存中提取一句精简洞察用于 greeting。"""
        if not todo.version_id:
            return ""
        try:
            from arc.application.planning.analysis_service import AnalysisService

            svc = AnalysisService(self.db)
            result = await svc.get_latest(todo.version_id)
            if not result:
                return ""

            _, suggestions = result
            if not suggestions:
                return ""

            # 提取与当前 todo 相关的建议（如有）或总体概况
            related = [
                s for s in suggestions
                if todo.title.lower() in s.get("action", "").lower()
            ]
            if related:
                s = related[0]
                return (
                    f"版本分析中对此需求的定位：**[{s.get('priority', '?')}]** "
                    f"{s.get('reason', s.get('action', ''))}"
                )

            # 无直接相关的，给出版本整体状况
            p0_count = sum(1 for s in suggestions if s.get("priority") == "P0")
            if p0_count:
                return f"当前版本有 {p0_count} 项 P0 优先事项，我会注意与它们的协调。"
            return ""
        except Exception:
            return ""

    async def _get_project_constraint(self, todo) -> str:
        """获取项目的 process_constraint 级别。"""
        if not todo or not todo.project_id:
            return "free"
        from arc.infrastructure.repositories.project import ProjectRepository
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return "free"
        return project.process_constraint.value

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

    async def _get_llm_config(self, todo_id: uuid.UUID) -> dict | None:
        """获取项目级 LLM 配置（conversation_config.llm）。"""
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return None
        return project.conversation_config.get("llm") or None

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

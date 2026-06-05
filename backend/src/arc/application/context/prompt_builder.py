"""上下文 & Prompt 构建模块。

v5.4+ 重构：
- build_system_prompt() 委托给 ContextAssembler（统一 Provider 管道）
- build_llm_messages() 保持向后兼容
- 旧的 _build_xxx 私有方法保留用于 pipeline 模式等特殊场景
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arc.domain.conversation.entity import Conversation
    from arc.domain.todo.entity import Todo

logger = logging.getLogger(__name__)


class PromptBuilder:
    """构建 LLM 消息列表和系统提示词。

    内部委托 ContextAssembler 进行模块化的上下文组装，
    集成 ContextController 进行 token 预算管理和压缩。
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._context_controller = None  # lazy init
        self._assembler = None  # lazy init
        self._injected_experience_ids: list[uuid.UUID] = []

    @property
    def injected_experience_ids(self) -> list[uuid.UUID]:
        """返回最近一次 build_llm_messages 注入的经验 ID 列表。"""
        return self._injected_experience_ids

    def _get_assembler(self):
        """延迟初始化 ContextAssembler。"""
        if self._assembler is None:
            from arc.application.context.assembler import ContextAssembler
            self._assembler = ContextAssembler(self._db)
        return self._assembler

    def _get_context_controller(self):
        """延迟初始化 ContextController + CompressionManager。"""
        if self._context_controller is None:
            from arc.application.context.compression import CompressionManager
            from arc.application.context.controller import ContextController

            compression = CompressionManager(adapter=None)
            self._context_controller = ContextController(
                compression=compression,
            )
        return self._context_controller

    async def build_llm_messages(
        self,
        conversation: Conversation,
    ) -> list:
        """将对话历史组装为 LLM 消息列表。

        使用 ContextAssembler 构建 system prompt，
        ContextController 管理 token 预算和压缩。
        """
        from arc.infrastructure.repositories.todo import TodoRepository

        todo_repo = TodoRepository(self._db)
        todo = await todo_repo.get_by_id(conversation.todo_id)

        system_prompt = await self.build_system_prompt(conversation, todo)

        # 经验上下文通过 Assembler 已注入 system prompt，
        # 但也作为 memory_context 传给 ContextController 做 P1 排序
        assembler = self._get_assembler()
        self._injected_experience_ids = list(assembler.injected_experience_ids)

        # 使用 ContextController 按 token 预算组装
        controller = self._get_context_controller()
        return await controller.assemble(
            system_prompt=system_prompt,
            messages=conversation.messages,
            memory_context="",  # 经验已在 system prompt 内
        )

    async def build_system_prompt(
        self,
        conversation: Conversation,
        todo: Todo | None,
        *,
        phase_scope: str | None = None,
    ) -> str:
        """组装完整的系统提示词 — 委托给 ContextAssembler。

        Args:
            phase_scope: 限定 deliverable 展示范围（pipeline 模式专用）。
                None → 走 ContextAssembler 全量组装
                "clarification" 等 → 回退到旧逻辑（pipeline 兼容）
        """
        # pipeline 模式仍用旧逻辑（phase_scope 限定交付物范围）
        if phase_scope:
            return await self._build_system_prompt_legacy(
                conversation, todo, phase_scope=phase_scope
            )

        # 对话模式 → ContextAssembler
        from arc.application.context.protocol import ContextRequest
        from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

        tracker_repo = DeliverableTrackerRepository(self._db)
        tracker = await tracker_repo.get_by_todo_id(conversation.todo_id)
        completed = [
            k
            for k, v in (tracker.deliverables if tracker else {}).items()
            if v.value in ("produced", "confirmed")
        ]

        # 推断当前阶段
        phase = self._infer_phase(completed)

        request = ContextRequest(
            todo=todo,
            conversation=conversation,
            phase=phase,
            completed_artifacts=completed,
            project_id=todo.project_id if todo else None,
        )

        assembler = self._get_assembler()
        return await assembler.assemble(request)

    # ------------------------------------------------------------------
    # Phase inference
    # ------------------------------------------------------------------

    @staticmethod
    def _infer_phase(completed: list[str]) -> str:
        """从已完成交付物推断当前阶段。"""
        if "requirement_spec" not in completed:
            return "clarification"
        if "interaction_design" not in completed and "ui_design" not in completed:
            return "ui_design"
        if "tech_architecture" not in completed:
            return "architecture"
        if "dev_report" not in completed:
            return "development"
        if "test_report" not in completed:
            return "testing"
        return "deployment"

    # ------------------------------------------------------------------
    # Legacy: pipeline 模式兼容
    # ------------------------------------------------------------------

    async def _build_system_prompt_legacy(
        self,
        conversation: Conversation,
        todo: Todo | None,
        *,
        phase_scope: str | None = None,
    ) -> str:
        """旧版 system prompt 组装 — 仅 pipeline 模式使用。"""
        from arc.application.context.prompts import (
            ARTIFACT_SCHEMAS,
            AUTOPILOT_SECTION,
            CONVERSATION_MODE_SYSTEM_PROMPT,
            build_ddd_tdd_section,
            build_deliverable_checklist,
        )
        from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType
        from arc.infrastructure.repositories.artifact import ArtifactRepository
        from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

        tracker_repo = DeliverableTrackerRepository(self._db)
        artifact_repo = ArtifactRepository(self._db)

        tracker = await tracker_repo.get_by_todo_id(conversation.todo_id)
        required = tracker.required if tracker else []
        completed = [
            k
            for k, v in (tracker.deliverables if tracker else {}).items()
            if v.value in ("produced", "confirmed")
        ]

        if phase_scope:
            from arc.domain.artifact.value_objects import PHASE_ARTIFACT_MAP
            from arc.domain.pipeline.value_objects import PhaseType

            try:
                pt = PhaseType(phase_scope)
                scoped_types = PHASE_ARTIFACT_MAP.get(pt, [])
                if scoped_types:
                    scoped_values = [t.value for t in scoped_types]
                    required = [v for v in scoped_values if v in required] or scoped_values
            except ValueError:
                pass

        # 交付物清单
        checklist = build_deliverable_checklist(required, completed)
        schemas = "\n".join(
            f"- **{ARTIFACT_LABELS.get(ArtifactType(t), t)}** (`{t}`):"
            f"\n```\n{ARTIFACT_SCHEMAS.get(t, '{}')}\n```"
            for t in required
            if t not in completed
        )
        deliverable_section = (
            f"## 交付物清单（渐进式完成）\n{checklist}\n\n"
            "## 交付物输出规则\n"
            "当你认为某个交付物内容已经充分时，使用以下格式输出：\n\n"
            "[DELIVERABLE:artifact_type]\n```json\n(结构化内容)\n```\n\n"
            f"可用的artifact_type及其schema：\n{schemas}"
        )

        # 项目上下文 + 领域模型
        project_context = ""
        if todo and todo.project_id:
            from arc.application.context.provider import ProjectContextProvider
            from arc.infrastructure.repositories.project import ProjectRepository

            ctx_provider = ProjectContextProvider(self._db)
            project_ctx = await ctx_provider.get_context(conversation.todo_id)
            project_context = project_ctx.to_prompt_section()

            project = await ProjectRepository(self._db).get_by_id(todo.project_id)
            if project and project.domain_model:
                ddd = build_ddd_tdd_section(project.domain_model)
                if ddd:
                    project_context += "\n\n" + ddd

        # 已完成交付物
        completed_text = "暂无"
        if completed:
            import json
            artifacts = await artifact_repo.list_by_todo_id(conversation.todo_id)
            parts = []
            for a in artifacts:
                if a.artifact_type.value in completed:
                    label = ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                    summary = json.dumps(a.content, ensure_ascii=False, indent=2)
                    if len(summary) > 500:
                        summary = summary[:500] + "..."
                    parts.append(f"### {label}\n{summary}")
            completed_text = "\n\n".join(parts) if parts else "暂无"

        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            methodology_section="",
            project_context=project_context,
            experience_context="",
            sufficiency_hint="",
            completed_artifacts=completed_text,
        )

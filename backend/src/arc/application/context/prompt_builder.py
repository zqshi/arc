"""上下文 & Prompt 构建模块。

从 conversation_strategy.py 提取。职责：
- 系统提示词组装
- LLM 消息列表构建
- 项目上下文 / 经验 / DDD / 交付物上下文注入
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING

from arc.application.context.prompts import (
    ARTIFACT_SCHEMAS,
    AUTOPILOT_SECTION,
    CONVERSATION_MODE_SYSTEM_PROMPT,
    build_ddd_tdd_section,
    build_deliverable_checklist,
)
from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arc.domain.conversation.entity import Conversation
    from arc.domain.planning.entity import DeliverableTracker
    from arc.domain.todo.entity import Todo

logger = logging.getLogger(__name__)


class PromptBuilder:
    """构建 LLM 消息列表和系统提示词。

    集成 ContextController 进行 token 预算管理和压缩。
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._context_controller = None  # lazy init
        self._injected_experience_ids: list[uuid.UUID] = []  # T3: 追踪注入的经验 ID

    @property
    def injected_experience_ids(self) -> list[uuid.UUID]:
        """返回最近一次 build_llm_messages 注入的经验 ID 列表。"""
        return self._injected_experience_ids

    def _get_context_controller(self):
        """延迟初始化 ContextController + CompressionManager。"""
        if self._context_controller is None:
            from arc.application.ai.adapter_pool import adapter_pool
            from arc.application.context.compression import CompressionManager
            from arc.application.context.controller import ContextController

            # CompressionManager 需要 LLM adapter 做 L2/L3 压缩
            # 使用 None — 首次无 adapter 时降级为截断
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

        使用 ContextController 管理 token 预算，必要时触发压缩。
        替换原来的 get_context_window(max_messages=50) 硬编码。
        """
        from arc.infrastructure.repositories.todo import TodoRepository

        todo_repo = TodoRepository(self._db)
        todo = await todo_repo.get_by_id(conversation.todo_id)

        system_prompt = await self.build_system_prompt(conversation, todo)

        # 获取经验上下文（作为 memory recall 注入）
        experience_text = await self._build_experience_context(todo)

        # 使用 ContextController 按 token 预算组装
        controller = self._get_context_controller()
        return await controller.assemble(
            system_prompt=system_prompt,
            messages=conversation.messages,
            memory_context=experience_text,
        )

    async def build_system_prompt(
        self,
        conversation: Conversation,
        todo: Todo | None,
        *,
        phase_scope: str | None = None,
    ) -> str:
        """组装完整的系统提示词。

        Args:
            phase_scope: 限定 deliverable 展示范围。
                None → 展示全部未完成 deliverable (conversation 模式)
                "clarification" → 只展示该阶段对应的 deliverable schema (pipeline 模式)
        """
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

        # phase_scope 限定展示范围
        if phase_scope:
            from arc.domain.artifact.value_objects import PHASE_ARTIFACT_MAP
            from arc.domain.pipeline.value_objects import PhaseType

            try:
                pt = PhaseType(phase_scope)
                scoped_type = PHASE_ARTIFACT_MAP.get(pt)
                if scoped_type:
                    scoped_value = scoped_type.value
                    required = [scoped_value] if scoped_value in required else [scoped_value]
            except ValueError:
                pass  # invalid phase_scope, use full list

        deliverable_section = self._build_deliverable_section(required, completed)
        project_context = await self._build_project_context(conversation, todo)
        # experience_context 现在通过 ContextController.assemble() 的
        # memory_context 参数注入，不再放在 system prompt 模板里
        experience_context = ""
        completed_artifacts_text = await self._build_completed_artifacts(
            artifact_repo, conversation.todo_id, completed
        )
        code_capability = await self._build_code_capability(conversation, todo)

        autonomy = await self._get_autonomy(todo)
        autopilot_section = AUTOPILOT_SECTION if autonomy == "full" else ""

        # 方法论注入 — 根据当前阶段和进度动态选择
        methodology_section = await self._build_methodology_section(
            conversation, todo, completed
        )

        # 充分性提示 — 需求阶段尚未产出时注入
        sufficiency_hint = ""
        if "requirement_spec" not in completed and todo:
            sufficiency_hint = await self._build_sufficiency_hint(conversation, todo)

        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            methodology_section=methodology_section,
            project_context=(
                project_context
                + code_capability
                + ("\n\n" + autopilot_section if autopilot_section else "")
            ),
            experience_context=experience_context,
            sufficiency_hint=sufficiency_hint,
            completed_artifacts=completed_artifacts_text,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_deliverable_section(
        required: list[str], completed: list[str]
    ) -> str:
        checklist = build_deliverable_checklist(required, completed)
        schemas = "\n".join(
            f"- **{ARTIFACT_LABELS.get(ArtifactType(t), t)}** (`{t}`):"
            f"\n```\n{ARTIFACT_SCHEMAS.get(t, '{}')}\n```"
            for t in required
            if t not in completed
        )
        return (
            f"## 交付物清单（渐进式完成）\n{checklist}\n\n"
            "## 交付物输出规则\n"
            "当你认为某个交付物内容已经充分时，使用以下格式输出：\n\n"
            "[DELIVERABLE:artifact_type]\n```json\n(结构化内容)\n```\n\n"
            f"可用的artifact_type及其schema：\n{schemas}"
        )

    async def _build_project_context(
        self, conversation: Conversation, todo: Todo | None
    ) -> str:
        if not todo or not todo.project_id:
            return ""

        from arc.application.context.provider import ProjectContextProvider
        from arc.infrastructure.repositories.project import ProjectRepository

        ctx_provider = ProjectContextProvider(self._db)
        project_ctx = await ctx_provider.get_context(conversation.todo_id)
        project_context = project_ctx.to_prompt_section()

        project = await ProjectRepository(self._db).get_by_id(todo.project_id)
        if project and project.domain_model:
            ddd = build_ddd_tdd_section(project.domain_model)
            if ddd:
                project_context = project_context + "\n\n" + ddd

        return project_context

    async def _build_experience_context(self, todo: Todo | None) -> str:
        """构建经验上下文，使用 MemoryScorer 五维打分排序。"""
        self._injected_experience_ids = []  # 每次重置
        if not todo:
            return ""
        try:
            from arc.application.experience.scorer import MemoryScorer
            from arc.infrastructure.repositories.experience import ExperienceRepository

            exp_repo = ExperienceRepository(self._db)

            # 获取候选经验（项目 + 全局范围）
            candidates = []
            if todo.project_id:
                project_exps = await exp_repo.list_by_project_id(
                    todo.project_id, limit=20,
                )
                candidates.extend(project_exps)

            # T6: 同时获取全局经验（跨项目共享的高质量经验）
            from arc.domain.todo.value_objects import ExperienceScope
            try:
                global_exps = await exp_repo.list_by_scope(
                    ExperienceScope.GLOBAL, limit=10,
                )
                seen_ids = {e.id for e in candidates}
                candidates.extend(e for e in global_exps if e.id not in seen_ids)
            except Exception:
                pass

            # 使用 MemoryScorer 打分排序
            scorer = MemoryScorer()

            # 尝试获取查询 embedding（用 todo 标题+描述）
            query_embedding = None
            try:
                from arc.application.ai.local_embedding import embed_local
                query_text = f"{todo.title} {todo.description or ''}"
                query_embedding = await embed_local(query_text)
            except Exception:
                pass

            if candidates:
                scored = scorer.score_batch(candidates, query_embedding)
                top_k = scored[:5]  # 取 Top-5

                parts = []
                for exp, score in top_k:
                    if score < 0.2:
                        continue
                    self._injected_experience_ids.append(exp.id)
                    parts.append(
                        f"### {exp.title} (相关度: {score:.2f})\n"
                        f"**问题**: {exp.problem}\n"
                        f"**方案**: {exp.solution}"
                    )
                if parts:
                    return "## 相关历史经验（按相关度排序）\n\n" + "\n\n".join(parts)

            # Fallback: 按 scope 获取经验列表（不需要 MemoryScorer）
            from arc.domain.todo.value_objects import ExperienceScope

            fallback_exps = await exp_repo.list_by_scope(
                ExperienceScope.PERSONAL, limit=5
            )
            if todo.project_id:
                proj_exps = await exp_repo.list_by_scope(
                    ExperienceScope.PROJECT, limit=5, project_id=todo.project_id
                )
                seen_ids = {e.id for e in fallback_exps}
                fallback_exps.extend(e for e in proj_exps if e.id not in seen_ids)

            if fallback_exps:
                parts = []
                for exp in fallback_exps[:5]:
                    parts.append(
                        f"### {exp.title}\n"
                        f"**问题**: {exp.problem}\n"
                        f"**方案**: {exp.solution}"
                    )
                return "## 相关历史经验\n" + "\n\n".join(parts)

        except Exception:
            pass
        return ""

    async def _build_completed_artifacts(
        self, artifact_repo, todo_id: uuid.UUID, completed: list[str]
    ) -> str:
        if not completed:
            return "暂无"
        artifacts = await artifact_repo.list_by_todo_id(todo_id)
        parts = []
        for a in artifacts:
            if a.artifact_type.value in completed:
                label = ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                summary = json.dumps(a.content, ensure_ascii=False, indent=2)
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                parts.append(f"### {label}\n{summary}")
        return "\n\n".join(parts) if parts else "暂无"

    async def _build_code_capability(
        self, conversation: Conversation, todo: Todo | None
    ) -> str:
        if not todo or not todo.project_id:
            return ""

        from pathlib import Path

        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self._db).get_by_id(todo.project_id)
        if not project or not project.local_path:
            return ""
        resolved = Path(project.local_path).expanduser().resolve()
        if not resolved.is_dir():
            return ""

        return f"""

## 代码操作能力（重要）
你可以直接操作项目代码。项目工作目录: `{resolved}`

可用工具：
- `list_directory` — 查看目录结构，了解项目全貌
- `read_file` — 阅读源码文件，支持指定行范围
- `grep_search` — 搜索代码中的文本/模式
- `run_command` — 执行 shell 命令（git/npm/pytest/ls 等）
- `write_file` — 创建或修改文件

需要了解代码时直接用工具读取，不要让用户贴代码。"""

    async def _get_autonomy(self, todo: Todo | None) -> str:
        if not todo or not todo.project_id:
            return "supervised"
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self._db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return "supervised"
        return project.conversation_config.get("agent_autonomy", "supervised")

    # ------------------------------------------------------------------
    # Methodology injection (Skill 集成)
    # ------------------------------------------------------------------

    async def _build_methodology_section(
        self, conversation: Conversation, todo: Todo | None, completed: list[str]
    ) -> str:
        """根据当前进度 + 项目 ProcessConstraint 动态注入方法论。

        三级差异:
        - strict: 完整方法论，逐步引导，每步独立 gate
        - moderate: 精简方法论，核心要点一次性给出
        - free: 不注入方法论（AI 自主决策）
        """
        from arc.application.execution.constraint_policy import (
            get_methodology_prompt_for_constraint,
        )
        from arc.domain.project.value_objects import ProcessConstraint

        # 获取项目的 process_constraint
        constraint = ProcessConstraint.FREE
        if todo and todo.project_id:
            from arc.infrastructure.repositories.project import ProjectRepository

            project = await ProjectRepository(self._db).get_by_id(todo.project_id)
            if project:
                constraint = project.process_constraint

        # 确定当前阶段
        if "requirement_spec" not in completed:
            phase = "clarification"
        elif "interaction_design" not in completed and "ui_design" not in completed:
            phase = "ui_design"
        elif "tech_architecture" not in completed:
            phase = "architecture"
        elif "dev_report" not in completed:
            phase = "development"
        elif "test_report" not in completed:
            phase = "testing"
        else:
            return ""

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        return get_methodology_prompt_for_constraint(constraint, phase, user_rounds)

    def _build_clarification_methodology(
        self, conversation: Conversation, todo: Todo | None
    ) -> str:
        """注入需求澄清策略 — 基于 decision-thinking-toolkit。"""
        from arc.application.execution.clarification_strategy import (
            build_clarification_prompt,
            route_strategy,
        )

        title = todo.title if todo else ""
        description = todo.description if todo else ""
        # 估算对话轮次 — 只计用户消息
        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        strategy = route_strategy(title, description, user_rounds)
        return build_clarification_prompt(strategy, user_rounds)

    def _build_architecture_methodology(self, conversation: Conversation) -> str:
        """注入架构方法论 — 基于 ddd-toolkit。"""
        from arc.application.execution.architecture_methodology import (
            get_methodology_overview,
            get_sub_phase_prompt,
        )

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        overview = get_methodology_overview()
        sub_phase = get_sub_phase_prompt(user_rounds)
        return f"{overview}\n\n{sub_phase}"

    def _build_ui_design_methodology(self, conversation: Conversation) -> str:
        """注入 UI 设计方法论 — 基于 frontend-design + ui-ux-pro-max。"""
        from arc.application.execution.ui_design_methodology import get_ui_design_prompt

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )
        return get_ui_design_prompt(user_rounds)

    def _build_development_methodology(self, conversation: Conversation) -> str:
        """注入开发方法论 — 基于 superpowers TDD + verification。"""
        from arc.application.execution.dev_test_methodology import get_development_prompt

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )
        return get_development_prompt(user_rounds)

    def _build_testing_methodology(self, conversation: Conversation) -> str:
        """注入测试方法论 — 基于 superpowers verification-before-completion。"""
        from arc.application.execution.dev_test_methodology import get_testing_prompt

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )
        return get_testing_prompt(user_rounds)

    async def _build_sufficiency_hint(
        self, conversation: Conversation, todo: Todo | None
    ) -> str:
        """构建充分性提示 — 需求阶段尚未产出时注入。

        轻量版: 不调用 LLM，仅基于对话轮次给出定性提示。
        完整版 check_sufficiency() 在产出物生成前由 ExecutionEngine 调用。
        """
        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        if user_rounds < 2:
            return (
                "[提示] 当前信息尚不充分，请先引导用户说清楚：目标用户是谁、"
                "要解决什么问题、大致想做什么。不要急于生成产出物。"
            )
        if user_rounds < 4:
            return (
                "[提示] 基本信息已初步收集，但可能仍有模糊点。"
                "继续追问以确保信息充分后再产出交付物。"
            )
        return ""


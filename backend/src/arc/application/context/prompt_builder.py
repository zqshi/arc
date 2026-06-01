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
    ) -> str:
        """组装完整的系统提示词。"""
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

        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            project_context=(
                project_context
                + code_capability
                + ("\n\n" + autopilot_section if autopilot_section else "")
            ),
            experience_context=experience_context,
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
        if not todo:
            return ""
        try:
            from arc.application.experience.scorer import MemoryScorer
            from arc.infrastructure.repositories.experience import ExperienceRepository

            exp_repo = ExperienceRepository(self._db)

            # 获取候选经验（个人 + 项目范围）
            candidates = []
            if todo.project_id:
                project_exps = await exp_repo.list_by_project_id(
                    todo.project_id, limit=20,
                )
                candidates.extend(project_exps)

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

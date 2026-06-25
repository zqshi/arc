from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.provider import ProjectContextProvider
from arc.application.pipeline.prompts import (
    PHASE_SYSTEM_PROMPTS,
)
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.conversation.entity import Conversation, Message
from arc.domain.experience.entity import Experience
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.value_objects import MessageRole
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.experience import ExperienceRepository
from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)

PURPOSE_TO_PHASE: dict[str, PhaseType] = {
    "clarification": PhaseType.CLARIFICATION,
    "ui_design": PhaseType.UI_DESIGN,
    "architecture": PhaseType.ARCHITECTURE,
    "development": PhaseType.DEVELOPMENT,
    "testing": PhaseType.TESTING,
    "deployment": PhaseType.DEPLOYMENT,
    "review": PhaseType.EXTRACTION,
}


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.todo_repo = TodoRepository(db)
        self.phase_repo = PipelinePhaseRepository(db)
        self.artifact_repo = ArtifactRepository(db)
        self.exp_repo = ExperienceRepository(db)
        self._last_experience_refs: list[dict] = []

    async def generate_response(self, conversation: Conversation) -> Message:
        from arc.application.ai.resilience import create_resilient_adapter

        adapter = create_resilient_adapter()
        try:
            llm_messages = await self._build_llm_messages(conversation)
            response = await adapter.chat(llm_messages)
        finally:
            await adapter.close()

        metadata: dict = {"model": response.model, "usage": response.usage}
        if self._last_experience_refs:
            metadata["referenced_experiences"] = self._last_experience_refs

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata=metadata,
        )
        return ai_message

    async def generate_response_stream(self, conversation: Conversation) -> AsyncIterator[dict]:
        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.execution.agent_loop import AgentLoop, LoopConfig

        llm_messages = await self._build_llm_messages(conversation)

        # 检测项目路径 — 有路径时升级为 ToolAwareLoop (解决 pipeline 能力倒挂)
        project_path = await self._get_project_local_path(conversation.todo_id)

        message_id = None
        full_content = ""
        loop_metrics: dict = {}

        if project_path:
            # Tool-aware path — 与 ExecutionEngine 同等能力
            async for event_dict in self._tool_aware_stream(llm_messages, project_path):
                if "message_id" in event_dict and event_dict.get("content"):
                    if message_id is None:
                        message_id = event_dict["message_id"]
                    full_content += event_dict["content"]
                if event_dict.get("event") == "complete_metrics":
                    loop_metrics = event_dict.get("metrics", {})
                    continue
                yield event_dict
        else:
            # Text-only fallback
            config = LoopConfig(
                max_continuations=2,
                max_validation_retries=0,
                max_tokens_per_call=16384,
                token_budget=60000,
                wall_timeout_seconds=180.0,
            )

            async with adapter_pool.acquire() as adapter:
                loop = AgentLoop(adapter, config)
                async for event in loop.run(llm_messages):
                    if event.type == "chunk":
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                        yield {"message_id": message_id, "content": event.content}
                    elif event.type == "complete":
                        full_content = event.content
                        loop_metrics = event.metadata.get("metrics", {})
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))

        if not message_id:
            message_id = str(uuid.uuid4())

        metadata: dict = {
            "message_id": message_id,
            "streamed": True,
            "agent_loop": loop_metrics,
            "mode": "pipeline_tool_aware" if project_path else "pipeline_text",
        }
        if self._last_experience_refs:
            metadata["referenced_experiences"] = self._last_experience_refs

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=full_content,
            metadata=metadata,
            id=uuid.UUID(message_id),
        )
        await self.conv_repo.add_message(conversation.id, ai_message)

    async def _build_llm_messages(self, conversation: Conversation) -> list:
        """Build LLM message list — 委托 PromptBuilder 构建 system prompt。

        Phase 2 统一: pipeline 模式也使用 PromptBuilder，通过 phase_scope
        参数限定展示范围（只展示当前阶段的 deliverable schema）。
        """
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.context.prompt_builder import PromptBuilder

        todo = await self.todo_repo.get_by_id(conversation.todo_id)
        phase_scope = PURPOSE_TO_PHASE.get(conversation.purpose.value)

        builder = PromptBuilder(self.db)
        system_prompt = await builder.build_system_prompt(
            conversation,
            todo,
            phase_scope=phase_scope.value if phase_scope else None,
        )

        messages = [LLMMessage(role="system", content=system_prompt)]
        for msg in conversation.get_context_window(max_messages=40):
            messages.append(LLMMessage(role=msg.role.value, content=msg.content))

        return messages

    async def _build_system_prompt(
        self, conversation: Conversation, todo, phase_type: PhaseType | None
    ) -> str:
        """DEPRECATED — 保留兼容，新代码请使用 PromptBuilder.build_system_prompt()。

        Includes prior artifacts, experience context, and project context.
        """
        if not phase_type:
            return "帮助用户完成当前任务。"

        project_ctx_provider = ProjectContextProvider(self.db)
        project_ctx = await project_ctx_provider.get_context(conversation.todo_id)

        confirmed = await self._get_confirmed_artifacts(conversation.todo_id)
        experience_context, experience_refs = await self._build_experience_context(todo, phase_type)

        self._last_experience_refs = experience_refs

        project_section = project_ctx.to_prompt_section()

        if phase_type == PhaseType.CLARIFICATION:
            prompt = self._build_clarification_prompt(conversation, todo, confirmed)
            if project_section:
                prompt += f"\n\n{project_section}"
            if experience_context:
                prompt += f"\n\n## 相关历史经验\n{experience_context}"
            return prompt

        template = PHASE_SYSTEM_PROMPTS.get(phase_type, "")
        format_args = self._build_format_args(confirmed, todo)

        try:
            prompt = template.format(**format_args)
        except KeyError:
            prompt = template

        # 方法论注入 — Pipeline 模式也享受方法论引导
        methodology = self._get_phase_methodology(phase_type, conversation)
        if methodology:
            prompt += f"\n\n{methodology}"

        if project_section:
            prompt += f"\n\n{project_section}"

        if experience_context:
            prompt += f"\n\n## 相关历史经验（基于语义匹配）\n{experience_context}"
            prompt += (
                "\n\n注意：以上经验仅供参考，请结合当前任务的实际情况使用。"
                "特别关注踩坑记录，避免重复犯错。"
            )

        return prompt

    @staticmethod
    def _get_phase_methodology(phase_type: PhaseType, conversation: Conversation) -> str:
        """为 Pipeline 模式的每个阶段注入对应方法论。"""
        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        if phase_type == PhaseType.UI_DESIGN:
            from arc.application.execution.ui_design_methodology import get_ui_design_prompt
            return get_ui_design_prompt(user_rounds)

        if phase_type == PhaseType.ARCHITECTURE:
            from arc.application.execution.architecture_methodology import (
                get_methodology_overview,
                get_sub_phase_prompt,
            )
            return f"{get_methodology_overview()}\n\n{get_sub_phase_prompt(user_rounds)}"

        if phase_type == PhaseType.DEVELOPMENT:
            from arc.application.execution.dev_test_methodology import get_development_prompt
            return get_development_prompt(user_rounds)

        if phase_type == PhaseType.TESTING:
            from arc.application.execution.dev_test_methodology import get_testing_prompt
            return get_testing_prompt(user_rounds)

        return ""

    def _build_clarification_prompt(self, conversation: Conversation, todo, confirmed: dict) -> str:
        """意图驱动澄清: 按需求类型路由到最佳策略 (第一性原理/价值评估/苏格拉底/信息收集)。

        替代原先固定6层苏格拉底——激活 clarification_strategy 三策略路由，
        根据需求关键词 (新业务/优化/...) + 对话轮次动态选择澄清方法论。
        """
        from arc.application.execution.clarification_strategy import (
            build_clarification_prompt as build_strategy_prompt,
            route_strategy,
        )

        user_rounds = sum(
            1 for m in conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )
        title = todo.title if todo else ""
        description = todo.description if todo else ""

        strategy = route_strategy(title, description, user_rounds)
        prompt = build_strategy_prompt(strategy, user_rounds)

        if todo:
            prompt += f"\n\n## 任务信息\n标题: {todo.title}"
            if todo.description:
                prompt += f"\n描述: {todo.description}"

        return prompt

    def _build_format_args(self, confirmed: dict, todo) -> dict:
        """Build format args from confirmed artifacts for template substitution."""
        args: dict[str, str] = {}

        req = confirmed.get(ArtifactType.REQUIREMENT_SPEC)
        if req:
            args["requirement_spec"] = json.dumps(req, ensure_ascii=False, indent=2)
            args["acceptance_criteria"] = req.get("acceptance_criteria", "未定义")
        else:
            args["requirement_spec"] = "（尚未生成）"
            args["acceptance_criteria"] = "（尚未定义）"

        ui = confirmed.get(ArtifactType.UI_DESIGN)
        args["ui_design"] = json.dumps(ui, ensure_ascii=False, indent=2) if ui else "（尚未生成）"

        arch = confirmed.get(ArtifactType.TECH_ARCHITECTURE)
        args["tech_architecture"] = (
            json.dumps(arch, ensure_ascii=False, indent=2) if arch else "（尚未生成）"
        )

        dev = confirmed.get(ArtifactType.DEV_REPORT)
        args["dev_report"] = (
            json.dumps(dev, ensure_ascii=False, indent=2) if dev else "（尚未生成）"
        )

        all_text = []
        for atype, content in confirmed.items():
            dumped = json.dumps(content, ensure_ascii=False, indent=2)
            all_text.append(f"## {atype.value}\n{dumped}")
        args["full_context"] = "\n\n".join(all_text) if all_text else "（无历史数据）"

        return args

    async def _get_confirmed_artifacts(self, todo_id: uuid.UUID) -> dict[ArtifactType, dict]:
        """Fetch all confirmed artifacts for context injection."""
        artifacts = await self.artifact_repo.list_confirmed_by_todo(todo_id)
        return {ArtifactType(a.artifact_type): a.content for a in artifacts}

    async def _build_experience_context(
        self, todo, phase_type: PhaseType
    ) -> tuple[str, list[dict]]:
        """Search and format related experiences for system prompt injection.

        Returns (formatted_text, referenced_experience_list).
        Only matches confirmed experiences.
        """
        from arc.domain.todo.value_objects import ExperienceScope

        all_experiences: list[Experience] = []
        project_id = todo.project_id if todo else None

        try:
            personal_exps = await self.exp_repo.list_by_scope(ExperienceScope.PERSONAL, limit=5)
            project_exps = await self.exp_repo.list_by_scope(
                ExperienceScope.PROJECT, limit=5, project_id=project_id
            )
            all_experiences.extend(personal_exps)
            all_experiences.extend(project_exps)
        except Exception as exc:
            logger.warning("Scope-based experience fetch failed: %s", exc)

        if todo:
            query_parts = [todo.title]
            if todo.description:
                query_parts.append(todo.description)
            query = " ".join(query_parts)
            try:
                from arc.application.experience.service import ExperienceService

                exp_svc = ExperienceService(self.db)
                todo_exps = await exp_svc.search_similar(
                    query,
                    limit=3,
                    project_id=project_id,
                )
                seen = {e.id for e in all_experiences}
                all_experiences.extend(e for e in todo_exps if e.id not in seen)
            except Exception as exc:
                logger.warning("Experience search failed: %s", exc)

        if not all_experiences:
            return "", []

        refs = [
            {"id": str(e.id), "title": e.title, "scope": e.scope.value} for e in all_experiences
        ]

        return self._format_experiences(all_experiences, phase_type), refs

    @staticmethod
    def _format_experiences(experiences: list[Experience], phase_type: PhaseType) -> str:
        """Format experience list for prompt injection, emphasizing phase-relevant info."""
        parts = []
        for i, exp in enumerate(experiences, 1):
            section = f"### 经验{i}: {exp.title}\n"
            section += f"**问题**: {exp.problem}\n"
            section += f"**方案**: {exp.solution}\n"

            if exp.pitfalls and phase_type in (
                PhaseType.ARCHITECTURE,
                PhaseType.DEVELOPMENT,
                PhaseType.TESTING,
            ):
                pitfall_text = "; ".join(p if isinstance(p, str) else str(p) for p in exp.pitfalls)
                section += f"**踩坑记录**: {pitfall_text}\n"

            if exp.decisions and phase_type in (
                PhaseType.CLARIFICATION,
                PhaseType.ARCHITECTURE,
                PhaseType.UI_DESIGN,
            ):
                decision_text = "; ".join(
                    d if isinstance(d, str) else str(d) for d in exp.decisions
                )
                section += f"**关键决策**: {decision_text}\n"

            if exp.applicable_scenarios:
                section += f"**适用场景**: {exp.applicable_scenarios}\n"

            parts.append(section)

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Tool-aware execution (解决 Pipeline 能力倒挂 — RFC-001 Phase 1)
    # ------------------------------------------------------------------

    async def _get_project_local_path(self, todo_id: uuid.UUID) -> str | None:
        """获取项目本地路径 — 有路径时启用 ToolAwareLoop。"""
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
        return None

    async def _tool_aware_stream(
        self,
        llm_messages: list,
        project_path: str,
    ) -> AsyncIterator[dict]:
        """Tool-aware 执行路径 — Pipeline 模式也具备工具执行能力。

        与 ExecutionEngine._tool_aware_stream() 同等能力:
        - 文件读写/命令执行
        - 漂移检测
        - 死循环检测
        """
        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.execution.drift_detector import DriftDetector
        from arc.application.execution.error_loop_detector import ErrorLoopDetector
        from arc.application.execution.llm_review import default_llm_review
        from arc.application.execution.tool_loop import ToolAwareLoop, ToolLoopEvent
        from arc.application.execution.tools import ToolRegistry

        registry = ToolRegistry(project_path)

        # 提取用户目标用于漂移检测
        user_goal = ""
        for m in reversed(llm_messages):
            if m.role == "user":
                user_goal = m.content[:500]
                break

        drift_detector = (
            DriftDetector(user_goal, llm_review_fn=default_llm_review)
            if user_goal
            else None
        )
        error_detector = ErrorLoopDetector(llm_review_fn=default_llm_review)

        message_id = str(uuid.uuid4())

        async with adapter_pool.acquire() as adapter:
            loop = ToolAwareLoop(
                adapter, registry,
                drift_detector=drift_detector,
                error_loop_detector=error_detector,
            )
            async for event in loop.run(llm_messages):
                for mapped in self._map_tool_event(event, message_id):
                    yield mapped

    @staticmethod
    def _map_tool_event(event, default_mid: str) -> list[dict]:
        """将 ToolLoopEvent 映射为前端 SSE 字典。"""
        results = []
        mid = event.metadata.get("message_id", default_mid)

        if event.type == "text_delta":
            results.append({"message_id": mid, "content": event.content})
        elif event.type == "tool_call":
            results.append({
                "message_id": mid,
                "event": "tool_call",
                "tool_name": event.content,
                "tool_input": event.metadata.get("input", {}),
                "round": event.metadata.get("round", 0),
            })
        elif event.type == "tool_result":
            results.append({
                "message_id": mid,
                "event": "tool_result",
                "tool_name": event.metadata.get("tool_name", ""),
                "output_preview": event.content,
                "is_error": event.metadata.get("is_error", False),
            })
        elif event.type == "complete":
            results.append({
                "event": "complete_metrics",
                "metrics": {
                    "tool_rounds": event.metadata.get("tool_rounds", 0),
                    "total_tokens": event.metadata.get("total_tokens", 0),
                    "elapsed_ms": event.metadata.get("elapsed_ms", 0),
                },
            })
        return results

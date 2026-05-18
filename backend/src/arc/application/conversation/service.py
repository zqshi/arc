from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.pipeline.prompts import (
    PHASE_SYSTEM_PROMPTS,
    SOCRATIC_LAYERS,
    build_clarification_prompt,
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

    async def generate_response_stream(
        self, conversation: Conversation
    ) -> AsyncIterator[dict]:
        from arc.application.ai.resilience import create_resilient_adapter

        adapter = create_resilient_adapter()
        try:
            llm_messages = await self._build_llm_messages(conversation)
            message_id = str(uuid.uuid4())
            full_content = ""

            async for chunk in adapter.chat_stream(llm_messages):
                full_content += chunk
                yield {"message_id": message_id, "content": chunk}
        finally:
            await adapter.close()

        metadata: dict = {"message_id": message_id, "streamed": True}
        if self._last_experience_refs:
            metadata["referenced_experiences"] = self._last_experience_refs

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=full_content,
            metadata=metadata,
        )
        await self.conv_repo.add_message(conversation.id, ai_message)

    async def _build_llm_messages(self, conversation: Conversation) -> list:
        """Build LLM message list with phase-specific prompt and prior artifacts."""
        from arc.application.ai.llm_adapter import LLMMessage

        messages = []
        todo = await self.todo_repo.get_by_id(conversation.todo_id)
        phase_type = PURPOSE_TO_PHASE.get(conversation.purpose.value)

        system_prompt = await self._build_system_prompt(conversation, todo, phase_type)
        messages.append(LLMMessage(role="system", content=system_prompt))

        for msg in conversation.get_context_window(max_messages=40):
            messages.append(LLMMessage(role=msg.role.value, content=msg.content))

        return messages

    async def _build_system_prompt(
        self, conversation: Conversation, todo, phase_type: PhaseType | None
    ) -> str:
        """Build phase-aware system prompt with prior artifacts, experience context, and project context."""
        if not phase_type:
            return "你是一个AI助手，帮助用户完成任务。"

        from arc.application.context.provider import ProjectContextProvider

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

        if project_section:
            prompt += f"\n\n{project_section}"

        if experience_context:
            prompt += f"\n\n## 相关历史经验（基于语义匹配）\n{experience_context}"
            prompt += (
                "\n\n注意：以上经验仅供参考，请结合当前任务的实际情况使用。"
                "特别关注踩坑记录，避免重复犯错。"
            )

        return prompt

    def _build_clarification_prompt(
        self, conversation: Conversation, todo, confirmed: dict
    ) -> str:
        """Build Socratic clarification prompt with layer awareness."""
        user_msgs = [
            m for m in conversation.messages if m.role == MessageRole.USER
        ]
        current_layer = min(len(user_msgs) // 2 + 1, len(SOCRATIC_LAYERS))

        collected_parts = []
        if todo:
            collected_parts.append(f"任务标题: {todo.title}")
            if todo.description:
                collected_parts.append(f"初始描述: {todo.description}")
        collected_info = "\n".join(collected_parts) if collected_parts else ""

        prompt = build_clarification_prompt(current_layer, collected_info)

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
            personal_exps = await self.exp_repo.list_by_scope(
                ExperienceScope.PERSONAL, limit=5
            )
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
                    query, limit=3, project_id=project_id,
                )
                seen = {e.id for e in all_experiences}
                all_experiences.extend(
                    e for e in todo_exps if e.id not in seen
                )
            except Exception as exc:
                logger.warning("Experience search failed: %s", exc)

        if not all_experiences:
            return "", []

        refs = [
            {"id": str(e.id), "title": e.title, "scope": e.scope.value}
            for e in all_experiences
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
                PhaseType.ARCHITECTURE, PhaseType.DEVELOPMENT, PhaseType.TESTING
            ):
                pitfall_text = "; ".join(
                    p if isinstance(p, str) else str(p) for p in exp.pitfalls
                )
                section += f"**踩坑记录**: {pitfall_text}\n"

            if exp.decisions and phase_type in (
                PhaseType.CLARIFICATION, PhaseType.ARCHITECTURE, PhaseType.UI_DESIGN
            ):
                decision_text = "; ".join(
                    d if isinstance(d, str) else str(d) for d in exp.decisions
                )
                section += f"**关键决策**: {decision_text}\n"

            if exp.applicable_scenarios:
                section += f"**适用场景**: {exp.applicable_scenarios}\n"

            parts.append(section)

        return "\n".join(parts)

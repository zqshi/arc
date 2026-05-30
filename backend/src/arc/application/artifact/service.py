from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.application.pipeline.prompts import PHASE_EXTRACTION_PROMPTS
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import PHASE_ARTIFACT_MAP, ArtifactType
from arc.domain.pipeline.value_objects import PhaseType
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository

logger = logging.getLogger(__name__)


class ArtifactService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.artifact_repo = ArtifactRepository(db)
        self.phase_repo = PipelinePhaseRepository(db)
        self.conv_repo = ConversationRepository(db)

    async def generate_from_conversation(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> Artifact | None:
        """Use LLM to extract structured artifact from a phase's conversation."""
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase or not phase.conversation_id:
            logger.error("generate_artifact: no conversation for phase %s", phase_type)
            return None

        conv = await self.conv_repo.get_by_id(phase.conversation_id)
        if not conv:
            return None

        extraction_prompt = PHASE_EXTRACTION_PROMPTS.get(phase_type)
        if not extraction_prompt:
            return None

        messages = []
        messages.append(
            LLMMessage(
                role="system",
                content="根据对话内容生成结构化输出。",
            )
        )
        for msg in conv.messages:
            if msg.role.value != "system":
                messages.append(LLMMessage(role=msg.role.value, content=msg.content))
        messages.append(LLMMessage(role="user", content=extraction_prompt))

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat(messages, temperature=0.3)
        finally:
            await adapter.close()

        content = extract_json(response.content)
        if content is None or not isinstance(content, dict):
            logger.error("generate_artifact: failed to parse response for %s", phase_type)
            return None

        from arc.application.pipeline.prompt_registry import prompt_registry

        content["_meta"] = {
            "prompt_version": prompt_registry.get_version(phase_type, "extraction"),
            "model": response.model,
            "usage": response.usage,
        }

        artifact_type = PHASE_ARTIFACT_MAP[phase_type]
        existing = await self.artifact_repo.get_by_phase_id(phase.id)

        if existing:
            existing.update_content(content)
            return await self.artifact_repo.update(existing)
        else:
            artifact = Artifact(
                todo_id=todo_id,
                phase_id=phase.id,
                artifact_type=artifact_type,
                content=content,
            )
            return await self.artifact_repo.create(artifact)

    async def update_content(self, artifact_id: uuid.UUID, new_content: dict) -> Artifact | None:
        """User edits artifact content."""
        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact:
            return None
        artifact.update_content(new_content)
        return await self.artifact_repo.update(artifact)

    async def confirm(self, artifact_id: uuid.UUID) -> Artifact | None:
        """Mark artifact as confirmed."""
        artifact = await self.artifact_repo.get_by_id(artifact_id)
        if not artifact:
            return None
        artifact.confirm()
        return await self.artifact_repo.update(artifact)

    async def get_confirmed_context(self, todo_id: uuid.UUID) -> dict[ArtifactType, dict]:
        """Get all confirmed artifacts for a todo, keyed by type."""
        artifacts = await self.artifact_repo.list_confirmed_by_todo(todo_id)
        return {a.artifact_type: a.content for a in artifacts}

    async def get_by_phase(self, todo_id: uuid.UUID, phase_type: PhaseType) -> Artifact | None:
        """Get the artifact for a specific phase."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            return None
        return await self.artifact_repo.get_by_phase_id(phase.id)

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.pipeline.prompts import (
    PHASE_GREETINGS,
)
from arc.domain.artifact.entity import Artifact
from arc.domain.conversation.entity import Conversation
from arc.domain.pipeline.entity import PipelinePhase
from arc.domain.pipeline.value_objects import (
    PHASE_LABELS,
    PHASE_ORDER,
    PhaseStatus,
    PhaseType,
    next_phase,
)
from arc.domain.agent.entity import AgentSession
from arc.domain.agent.value_objects import AgentType
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole, TodoStatus
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.pipeline import PipelinePhaseRepository
from arc.infrastructure.repositories.todo import TodoRepository

AGENT_EXECUTION_PHASES = {PhaseType.DEVELOPMENT, PhaseType.TESTING, PhaseType.DEPLOYMENT}

logger = logging.getLogger(__name__)

PHASE_TO_CONV_PURPOSE: dict[PhaseType, ConversationPurpose] = {
    PhaseType.CLARIFICATION: ConversationPurpose.CLARIFICATION,
    PhaseType.UI_DESIGN: ConversationPurpose.UI_DESIGN,
    PhaseType.ARCHITECTURE: ConversationPurpose.ARCHITECTURE,
    PhaseType.DEVELOPMENT: ConversationPurpose.DEVELOPMENT,
    PhaseType.TESTING: ConversationPurpose.TESTING,
    PhaseType.DEPLOYMENT: ConversationPurpose.DEPLOYMENT,
    PhaseType.EXTRACTION: ConversationPurpose.REVIEW,
}


class PipelineService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.phase_repo = PipelinePhaseRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.artifact_repo = ArtifactRepository(db)

    async def initialize_pipeline(self, todo_id: uuid.UUID) -> list[PipelinePhase]:
        """Create all 7 phase instances for a todo and activate the first one."""
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        existing = await self.phase_repo.list_by_todo_id(todo_id)
        if existing:
            return existing

        phases = []
        for phase_type in PhaseType:
            phase = PipelinePhase(
                todo_id=todo_id,
                phase_type=phase_type,
            )
            phases.append(phase)

        created = await self.phase_repo.create_batch(phases)

        first = created[0]
        first.activate()
        await self.phase_repo.update(first)

        if todo.status == TodoStatus.PENDING:
            todo.start_pipeline()
        else:
            todo.current_phase = PhaseType.CLARIFICATION
            todo.updated_at = todo.updated_at
        await self.todo_repo.update(todo)

        return created

    async def start_phase(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> PipelinePhase:
        """Activate a phase and create its conversation."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise ValueError(f"Phase {phase_type} not found for todo {todo_id}")

        if phase.status == PhaseStatus.ACTIVE and phase.conversation_id:
            return phase

        if phase.status == PhaseStatus.PENDING:
            all_phases = await self.phase_repo.list_by_todo_id(todo_id)
            current_order = PHASE_ORDER[phase_type]
            for p in all_phases:
                p_order = PHASE_ORDER[p.phase_type]
                if p_order < current_order and p.status not in (PhaseStatus.CONFIRMED, PhaseStatus.SKIPPED):
                    raise ValueError(
                        f"请先完成「{PHASE_LABELS[p.phase_type]}」阶段后再开始「{PHASE_LABELS[phase_type]}」"
                    )
            phase.activate()

        purpose = PHASE_TO_CONV_PURPOSE[phase_type]
        conv = Conversation(
            todo_id=todo_id,
            purpose=purpose,
        )

        todo = await self.todo_repo.get_by_id(todo_id)
        conv.add_message(
            role=MessageRole.SYSTEM,
            content=f"开始「{todo.title if todo else ''}」的{phase_type.value}阶段。",
        )

        greeting_template = PHASE_GREETINGS.get(phase_type)
        if greeting_template and todo:
            greeting = greeting_template.format(title=todo.title)
            conv.add_message(role=MessageRole.ASSISTANT, content=greeting)

        await self.conv_repo.create(conv)

        phase.conversation_id = conv.id
        await self.phase_repo.update(phase)

        if todo:
            todo.update_phase(phase_type)
            await self.todo_repo.update(todo)

        return phase

    async def generate_artifact(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> Artifact | None:
        """AI extracts artifact from the phase conversation."""
        from arc.application.artifact.service import ArtifactService

        svc = ArtifactService(self.db)
        artifact = await svc.generate_from_conversation(todo_id, phase_type)

        if artifact:
            phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
            if phase and phase.status == PhaseStatus.ACTIVE:
                phase.mark_awaiting_confirm()
                await self.phase_repo.update(phase)

        return artifact

    async def confirm_phase(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> PipelinePhase | None:
        """Confirm current phase's artifact and advance to next phase.

        Raises PhaseGateError if the artifact doesn't meet quality gates.
        Uses a savepoint so all DB changes roll back atomically on failure.
        """
        from arc.application.pipeline.gate import PhaseGateError, evaluate_gate

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            return None

        artifact = await self.artifact_repo.get_by_phase_id(phase.id)
        if not artifact:
            from arc.application.pipeline.gate import GateResult
            raise PhaseGateError(GateResult(
                passed=False, score=0, gaps=["尚未生成产出物"],
                suggestion="请先与AI对话并生成产出物，再进行确认。",
            ))

        from arc.application.context.provider import ProjectContextProvider
        project_ctx = await ProjectContextProvider(self.db).get_context(todo_id)
        conventions = project_ctx.conventions if project_ctx.has_project else ""

        gate_result = await evaluate_gate(phase_type, artifact.content, conventions)
        if not gate_result.passed:
            raise PhaseGateError(gate_result)

        async with self.db.begin_nested():
            await self._feedback_experience_confidence(gate_result.score)

            if not artifact.is_confirmed:
                artifact.confirm()
                await self.artifact_repo.update(artifact)

            phase.confirm()
            await self.phase_repo.update(phase)

            nxt = next_phase(phase_type)
            if nxt:
                next_p = await self.phase_repo.get_by_todo_and_type(todo_id, nxt)
                if next_p and next_p.status == PhaseStatus.PENDING:
                    next_p.activate()
                    await self.phase_repo.update(next_p)

                todo = await self.todo_repo.get_by_id(todo_id)
                if todo and nxt:
                    todo.update_phase(nxt)
                    await self.todo_repo.update(todo)
            else:
                todo = await self.todo_repo.get_by_id(todo_id)
                if todo:
                    await self._extract_experience(todo)
                    todo.complete()
                    await self.todo_repo.update(todo)

        return phase

    async def skip_phase(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> PipelinePhase | None:
        """Skip a phase and activate the next one.

        Raises ValueError if the phase is not skippable.
        """
        from arc.application.pipeline.gate import can_skip

        if not can_skip(phase_type):
            raise ValueError(f"{phase_type.value}阶段不可跳过，请完成后再推进")

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            return None

        phase.skip()
        await self.phase_repo.update(phase)

        nxt = next_phase(phase_type)
        if nxt:
            next_p = await self.phase_repo.get_by_todo_and_type(todo_id, nxt)
            if next_p and next_p.status == PhaseStatus.PENDING:
                next_p.activate()
                await self.phase_repo.update(next_p)

            todo = await self.todo_repo.get_by_id(todo_id)
            if todo:
                todo.update_phase(nxt)
                await self.todo_repo.update(todo)

        return phase

    async def rollback_to(
        self, todo_id: uuid.UUID, target_phase: PhaseType
    ) -> PipelinePhase | None:
        """Rollback to a previous phase. Resets all subsequent phases."""
        target_order = PHASE_ORDER[target_phase]
        phases = await self.phase_repo.list_by_todo_id(todo_id)

        target = None
        for p in phases:
            order = PHASE_ORDER[p.phase_type]
            if p.phase_type == target_phase:
                p.reset_for_rollback()
                await self.phase_repo.update(p)
                target = p
            elif order > target_order:
                if p.status in (PhaseStatus.CONFIRMED, PhaseStatus.ACTIVE, PhaseStatus.AWAITING_CONFIRM):
                    p.status = PhaseStatus.PENDING
                    p.updated_at = p.updated_at  # trigger update
                    await self.phase_repo.update(p)
                artifact = await self.artifact_repo.get_by_phase_id(p.id)
                if artifact:
                    artifact.unconfirm()
                    await self.artifact_repo.update(artifact)

        if target:
            todo = await self.todo_repo.get_by_id(todo_id)
            if todo:
                todo.update_phase(target_phase)
                await self.todo_repo.update(todo)

        return target

    async def execute_with_agent(
        self,
        todo_id: uuid.UUID,
        phase_type: PhaseType,
        agent_type: AgentType | None = None,
    ) -> AgentSession:
        """Trigger coding agent execution for an execution phase."""
        if phase_type not in AGENT_EXECUTION_PHASES:
            raise ValueError(f"{phase_type.value}阶段不支持Agent执行")

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise ValueError(f"Phase {phase_type} not found for todo {todo_id}")

        if phase.status == PhaseStatus.PENDING:
            await self.start_phase(todo_id, phase_type)

        from arc.application.agent.session_manager import AgentSessionManager
        manager = AgentSessionManager(self.db)
        return await manager.start_session(todo_id, phase_type, agent_type)

    async def get_agent_session(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> AgentSession | None:
        """Get the agent session for a phase, if any."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase or not phase.agent_session_id:
            return None

        from arc.infrastructure.repositories.agent import AgentSessionRepository
        agent_repo = AgentSessionRepository(self.db)
        return await agent_repo.get_by_id(phase.agent_session_id)

    async def cancel_agent(
        self, todo_id: uuid.UUID, phase_type: PhaseType
    ) -> AgentSession | None:
        """Cancel the running agent session for a phase."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase or not phase.agent_session_id:
            return None

        from arc.application.agent.session_manager import AgentSessionManager
        manager = AgentSessionManager(self.db)
        return await manager.cancel_session(phase.agent_session_id)

    async def get_pipeline_state(self, todo_id: uuid.UUID) -> dict:
        """Get complete pipeline state for a todo."""
        phases = await self.phase_repo.list_by_todo_id(todo_id)
        artifacts = await self.artifact_repo.list_by_todo_id(todo_id)
        todo = await self.todo_repo.get_by_id(todo_id)

        return {
            "todo_id": str(todo_id),
            "current_phase": todo.current_phase.value if todo and todo.current_phase else None,
            "phases": [
                {
                    "id": str(p.id),
                    "phase_type": p.phase_type.value,
                    "status": p.status.value,
                    "conversation_id": str(p.conversation_id) if p.conversation_id else None,
                }
                for p in phases
            ],
            "artifacts": [
                {
                    "id": str(a.id),
                    "phase_id": str(a.phase_id),
                    "artifact_type": a.artifact_type.value,
                    "content": a.content,
                    "version": a.version,
                    "is_confirmed": a.is_confirmed,
                }
                for a in artifacts
            ],
        }

    async def _extract_experience(self, todo) -> None:
        from arc.application.experience.service import ExperienceService

        try:
            svc = ExperienceService(self.db)
            await svc.extract_from_todo(todo)
        except Exception as exc:
            logger.warning("Experience extraction failed for todo %s: %s", todo.id, exc)

    async def _feedback_experience_confidence(self, gate_score: int) -> None:
        """Update confidence of recently-reused experiences based on gate score."""
        from arc.infrastructure.repositories.experience import ExperienceRepository

        exp_repo = ExperienceRepository(self.db)
        try:
            reused = await exp_repo.list_recently_reused(limit=5)
            if not reused:
                return
            normalized = gate_score / 10.0
            for exp in reused:
                old = exp.confidence
                exp.update_confidence(
                    round(old * 0.7 + normalized * 0.3, 3)
                )
                await exp_repo.update(exp)
        except Exception as exc:
            logger.warning("Experience confidence feedback failed: %s", exc)

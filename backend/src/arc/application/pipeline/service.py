from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.pipeline import hooks as pipeline_hooks
from arc.application.pipeline.prompts import (
    PHASE_GREETINGS,
)
from arc.domain.agent.entity import AgentSession
from arc.domain.agent.value_objects import AgentType
from arc.domain.artifact.entity import Artifact
from arc.domain.conversation.entity import Conversation
from arc.domain.errors import AppError, NotFoundError
from arc.domain.pipeline.entity import PipelinePhase
from arc.domain.pipeline.value_objects import (
    PHASE_LABELS,
    PHASE_ORDER,
    PhaseStatus,
    PhaseType,
    next_phase,
)
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
            raise NotFoundError(f"Todo {todo_id} not found")

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

    async def start_phase(self, todo_id: uuid.UUID, phase_type: PhaseType) -> PipelinePhase:
        """Activate a phase and create its conversation."""
        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise NotFoundError(f"Phase {phase_type} not found for todo {todo_id}")

        if phase.status == PhaseStatus.ACTIVE and phase.conversation_id:
            return phase

        if phase.status == PhaseStatus.PENDING:
            all_phases = await self.phase_repo.list_by_todo_id(todo_id)
            current_order = PHASE_ORDER[phase_type]
            for p in all_phases:
                p_order = PHASE_ORDER[p.phase_type]
                if p_order < current_order and p.status not in (
                    PhaseStatus.CONFIRMED,
                    PhaseStatus.SKIPPED,
                ):
                    raise AppError(
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

    async def generate_artifact(self, todo_id: uuid.UUID, phase_type: PhaseType) -> Artifact | None:
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
        from arc.application.pipeline.gate import GateResult, PhaseGateError

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            return None

        artifact = await self.artifact_repo.get_by_phase_id(phase.id)
        if not artifact:
            raise PhaseGateError(
                GateResult(
                    passed=False,
                    score=0,
                    gaps=["尚未生成产出物"],
                    suggestion="请先与AI对话并生成产出物，再进行确认。",
                )
            )

        gate_result = await self._evaluate_phase_gate(phase_type, artifact, todo_id)
        if not gate_result.passed:
            raise PhaseGateError(gate_result)

        async with self.db.begin_nested():
            await self._confirm_and_advance(todo_id, phase_type, phase, artifact, gate_result)

        return phase

    async def _evaluate_phase_gate(
        self, phase_type: PhaseType, artifact: Artifact, todo_id: uuid.UUID
    ):
        """收集项目规范 + 前置产出物, 评估阶段质量 gate。

        v6.15: 先过 DAG 依赖守卫 (三档共享硬不变量), 再走 evaluate_gate。
        覆盖 skip 阶段后产出依赖未满足 artifact 的缺口——phase 顺序检查只拦
        "前置 phase 是否完成", 不拦 "前置交付物是否达标"; skip 掉 UI_DESIGN
        直接 confirm ARCHITECTURE 时, phase 顺序放行但 prototype 依赖未满足,
        DAG 在此硬阻断。
        """
        from arc.application.context.provider import ProjectContextProvider
        from arc.application.pipeline.gate import GateResult, evaluate_gate
        from arc.domain.planning.dependency_graph import missing_prerequisites

        project_ctx = await ProjectContextProvider(self.db).get_context(todo_id)
        conventions = project_ctx.conventions if project_ctx.has_project else ""

        # 收集前置已确认产出物 — DAG 依赖守卫 + 交叉一致性检查共用
        prior_artifacts = await pipeline_hooks.collect_prior_artifacts(
            self.artifact_repo, todo_id, phase_type
        )

        # DAG 依赖守卫 — 与 FREE 链路 (artifact_extractor) 同一真相源, 硬阻断
        missing = missing_prerequisites(
            artifact.artifact_type.value, set(prior_artifacts.keys())
        )
        if missing:
            return GateResult(
                passed=False,
                score=0,
                gaps=[
                    f"前置交付物未达标: {', '.join(missing)}；"
                    f"请先完成并达标后再确认 {artifact.artifact_type.value}"
                ],
                suggestion="先产出并完善前置交付物。",
            )

        return await evaluate_gate(
            phase_type, artifact.content, conventions,
            prior_artifacts=prior_artifacts,
        )

    async def _confirm_and_advance(
        self, todo_id, phase_type, phase, artifact, gate_result
    ) -> PipelinePhase:
        """事务内: 确认产出物+阶段 → 触发阶段副作用 → 推进下一阶段或完成。"""
        await pipeline_hooks.feedback_experience_confidence(self.db, gate_result.score)

        if not artifact.is_confirmed:
            artifact.confirm()
            await self.artifact_repo.update(artifact)

        phase.confirm()
        await self.phase_repo.update(phase)

        await self._trigger_phase_side_effects(todo_id, phase_type, artifact)

        nxt = next_phase(phase_type)
        if nxt:
            await self._advance_to_next(todo_id, nxt)
        else:
            await self._complete_pipeline(todo_id)
        return phase

    async def _trigger_phase_side_effects(
        self, todo_id: uuid.UUID, phase_type: PhaseType, artifact: Artifact
    ) -> None:
        """阶段确认后的特殊副作用: 架构合并领域模型 / 部署触发真实部署。"""
        if phase_type == PhaseType.ARCHITECTURE:
            # 架构阶段确认后 → 自动合并领域模型
            await pipeline_hooks.merge_domain_model(self.db, todo_id, artifact.content)
        elif phase_type == PhaseType.DEPLOYMENT:
            # 部署阶段确认后 → 触发真实部署 (build 未就绪转 PhaseGateError 回滚)
            from arc.application.execution.build_gate import BuildGateError
            from arc.application.pipeline.gate import GateResult, PhaseGateError

            try:
                await pipeline_hooks.trigger_deployment(
                    self.db, self.todo_repo, todo_id, artifact.content
                )
            except BuildGateError as exc:
                raise PhaseGateError(
                    GateResult(
                        passed=False,
                        score=0,
                        gaps=[f"部署前置构建未就绪: {exc}"],
                        suggestion=(
                            "请先完成构建并确认产物 (build_status=success) "
                            "后再确认部署阶段。"
                        ),
                    )
                )

    async def _advance_to_next(self, todo_id: uuid.UUID, nxt: PhaseType) -> None:
        """激活下一阶段 + 更新 todo 当前阶段。"""
        next_p = await self.phase_repo.get_by_todo_and_type(todo_id, nxt)
        if next_p and next_p.status == PhaseStatus.PENDING:
            next_p.activate()
            await self.phase_repo.update(next_p)

        todo = await self.todo_repo.get_by_id(todo_id)
        if todo and nxt:
            todo.update_phase(nxt)
            await self.todo_repo.update(todo)

    async def _complete_pipeline(self, todo_id: uuid.UUID) -> None:
        """末尾阶段: 提取经验 + 完成 todo + 通知 GitHub。"""
        todo = await self.todo_repo.get_by_id(todo_id)
        if todo:
            await pipeline_hooks.extract_experience(self.db, todo)
            todo.complete()
            await self.todo_repo.update(todo)
            await pipeline_hooks.notify_github(self.db, todo)

    async def skip_phase(self, todo_id: uuid.UUID, phase_type: PhaseType) -> PipelinePhase | None:
        """Skip a phase and activate the next one.

        Raises ValueError if the phase is not skippable.
        """
        from arc.application.pipeline.gate import can_skip

        if not can_skip(phase_type):
            raise AppError(f"{phase_type.value}阶段不可跳过，请完成后再推进")

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
                if p.status in (
                    PhaseStatus.CONFIRMED,
                    PhaseStatus.ACTIVE,
                    PhaseStatus.AWAITING_CONFIRM,
                ):
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
            raise AppError(f"{phase_type.value}阶段不支持Agent执行")

        phase = await self.phase_repo.get_by_todo_and_type(todo_id, phase_type)
        if not phase:
            raise NotFoundError(f"Phase {phase_type} not found for todo {todo_id}")

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

    async def cancel_agent(self, todo_id: uuid.UUID, phase_type: PhaseType) -> AgentSession | None:
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


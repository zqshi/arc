"""Tests for application/pipeline service — initialization & state logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.pipeline.entity import PipelinePhase
from arc.domain.pipeline.value_objects import PhaseStatus, PhaseType
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus


class _FakeSavepoint:
    """模拟 async with db.begin_nested() 的 savepoint (不吞异常, 让其传播回滚)。"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class TestPipelineServiceInit:
    """Test pipeline initialization logic without DB."""

    def test_phase_order(self):
        """Verify the canonical phase execution order."""
        from arc.domain.pipeline.value_objects import PHASE_ORDER
        assert PhaseType.CLARIFICATION in PHASE_ORDER
        assert PhaseType.DEVELOPMENT in PHASE_ORDER
        # Clarification should have lower order number than development
        assert PHASE_ORDER[PhaseType.CLARIFICATION] < PHASE_ORDER[PhaseType.DEVELOPMENT]

    def test_phase_type_values(self):
        """All phase types should be valid string enums."""
        for pt in PhaseType:
            assert isinstance(pt.value, str)
            assert len(pt.value) > 0


@pytest.fixture
def pipeline_mocks():
    """patch confirm_phase 的所有外部依赖 (hooks graceful, 全 mock 不真实执行)。"""
    targets = {
        "evaluate_gate": "arc.application.pipeline.gate.evaluate_gate",
        "ProjectContextProvider": "arc.application.context.provider.ProjectContextProvider",
        "collect_prior_artifacts": "arc.application.pipeline.hooks.collect_prior_artifacts",
        "feedback_experience_confidence": "arc.application.pipeline.hooks.feedback_experience_confidence",
        "merge_domain_model": "arc.application.pipeline.hooks.merge_domain_model",
        "trigger_deployment": "arc.application.pipeline.hooks.trigger_deployment",
        "extract_experience": "arc.application.pipeline.hooks.extract_experience",
        "notify_github": "arc.application.pipeline.hooks.notify_github",
    }
    patches = {}
    mocks = {}
    for k, v in targets.items():
        # ProjectContextProvider 是类: ProjectContextProvider(db) 返回实例, 用 MagicMock
        # 其余 hooks 是 async 函数, 用 AsyncMock
        new = MagicMock() if k == "ProjectContextProvider" else AsyncMock()
        p = patch(v, new=new)
        patches[k] = p
        mocks[k] = p.start()
    mocks["collect_prior_artifacts"].return_value = {}
    mocks["evaluate_gate"].return_value = MagicMock(passed=True, score=8)
    ctx = MagicMock()
    ctx.has_project = False
    ctx.conventions = ""
    mocks["ProjectContextProvider"].return_value.get_context = AsyncMock(return_value=ctx)
    yield mocks
    for p in patches.values():
        p.stop()


def _make_svc(*, current_phase, artifact, todo=None, next_phase=None):
    """构造 PipelineService (跳过 __init__), mock 4 repo + 事务 savepoint。"""
    from arc.application.pipeline.service import PipelineService

    svc = PipelineService.__new__(PipelineService)
    svc.db = MagicMock()
    svc.db.begin_nested = MagicMock(return_value=_FakeSavepoint())

    async def _get_phase(_tid, pt: PhaseType):
        if current_phase is not None and pt == current_phase.phase_type:
            return current_phase
        if next_phase is not None and pt == next_phase.phase_type:
            return next_phase
        return None

    svc.phase_repo = MagicMock()
    svc.phase_repo.get_by_todo_and_type = AsyncMock(side_effect=_get_phase)
    svc.phase_repo.update = AsyncMock()

    svc.artifact_repo = MagicMock()
    svc.artifact_repo.get_by_phase_id = AsyncMock(return_value=artifact)
    svc.artifact_repo.update = AsyncMock()

    svc.todo_repo = MagicMock()
    svc.todo_repo.get_by_id = AsyncMock(return_value=todo)
    svc.todo_repo.update = AsyncMock()
    return svc


def _make_phase(phase_type: PhaseType, status=PhaseStatus.AWAITING_CONFIRM) -> PipelinePhase:
    return PipelinePhase(todo_id=uuid.uuid4(), phase_type=phase_type, status=status)


def _make_artifact() -> Artifact:
    return Artifact(
        todo_id=uuid.uuid4(), artifact_type=ArtifactType.APP_CODE, content={"k": "v"},
    )


def _make_todo() -> Todo:
    return Todo(title="t", description="d", id=uuid.uuid4(), status=TodoStatus.ACTIVE)


class TestPipelineServiceConfirmPhase:
    """confirm_phase — 确认+gate+事务编排+阶段推进 characterization。"""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_phase(self, pipeline_mocks):
        svc = _make_svc(current_phase=None, artifact=None)
        result = await svc.confirm_phase(uuid.uuid4(), PhaseType.DEVELOPMENT)
        assert result is None
        pipeline_mocks["evaluate_gate"].assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_phase_gate_error_when_no_artifact(self, pipeline_mocks):
        from arc.application.pipeline.gate import PhaseGateError

        phase = _make_phase(PhaseType.DEVELOPMENT)
        svc = _make_svc(current_phase=phase, artifact=None)
        with pytest.raises(PhaseGateError) as exc_info:
            await svc.confirm_phase(uuid.uuid4(), PhaseType.DEVELOPMENT)
        assert "尚未生成产出物" in exc_info.value.result.gaps[0]

    @pytest.mark.asyncio
    async def test_raises_when_gate_failed(self, pipeline_mocks):
        from arc.application.pipeline.gate import GateResult, PhaseGateError

        pipeline_mocks["evaluate_gate"].return_value = GateResult(
            passed=False, score=2, gaps=["缺字段"], suggestion="补充X",
        )
        phase = _make_phase(PhaseType.DEVELOPMENT)
        svc = _make_svc(current_phase=phase, artifact=_make_artifact())
        with pytest.raises(PhaseGateError) as exc_info:
            await svc.confirm_phase(uuid.uuid4(), PhaseType.DEVELOPMENT)
        assert exc_info.value.result.passed is False

    @pytest.mark.asyncio
    async def test_confirms_and_advances_to_next(self, pipeline_mocks):
        phase = _make_phase(PhaseType.DEVELOPMENT)
        artifact = _make_artifact()
        next_p = _make_phase(PhaseType.TESTING, status=PhaseStatus.PENDING)
        todo = _make_todo()
        svc = _make_svc(
            current_phase=phase, artifact=artifact, todo=todo, next_phase=next_p,
        )

        result = await svc.confirm_phase(uuid.uuid4(), PhaseType.DEVELOPMENT)

        assert result is phase
        assert artifact.is_confirmed is True
        assert phase.status == PhaseStatus.CONFIRMED
        assert next_p.status == PhaseStatus.ACTIVE
        pipeline_mocks["feedback_experience_confidence"].assert_awaited_once()
        # 非 ARCHITECTURE/DEPLOYMENT, 不触发特殊副作用
        pipeline_mocks["merge_domain_model"].assert_not_awaited()
        pipeline_mocks["trigger_deployment"].assert_not_awaited()
        # 有下一阶段, 不走 complete 路径
        pipeline_mocks["extract_experience"].assert_not_awaited()
        svc.todo_repo.update.assert_awaited()  # todo.update_phase

    @pytest.mark.asyncio
    async def test_merges_domain_model_on_architecture(self, pipeline_mocks):
        phase = _make_phase(PhaseType.ARCHITECTURE)
        artifact = _make_artifact()
        next_p = _make_phase(PhaseType.DEVELOPMENT, status=PhaseStatus.PENDING)
        svc = _make_svc(
            current_phase=phase, artifact=artifact, todo=_make_todo(), next_phase=next_p,
        )
        await svc.confirm_phase(uuid.uuid4(), PhaseType.ARCHITECTURE)
        pipeline_mocks["merge_domain_model"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_triggers_deployment_on_deployment_phase(self, pipeline_mocks):
        phase = _make_phase(PhaseType.DEPLOYMENT)
        artifact = _make_artifact()
        svc = _make_svc(
            current_phase=phase, artifact=artifact, todo=_make_todo(), next_phase=None,
        )
        await svc.confirm_phase(uuid.uuid4(), PhaseType.DEPLOYMENT)
        pipeline_mocks["trigger_deployment"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_phase_gate_error_on_build_not_ready(self, pipeline_mocks):
        from arc.application.execution.build_gate import BuildGateError
        from arc.application.pipeline.gate import PhaseGateError

        pipeline_mocks["trigger_deployment"].side_effect = BuildGateError("build not ready")
        phase = _make_phase(PhaseType.DEPLOYMENT)
        artifact = _make_artifact()
        svc = _make_svc(
            current_phase=phase, artifact=artifact, todo=_make_todo(), next_phase=None,
        )
        with pytest.raises(PhaseGateError) as exc_info:
            await svc.confirm_phase(uuid.uuid4(), PhaseType.DEPLOYMENT)
        assert "部署前置构建未就绪" in exc_info.value.result.gaps[0]

    @pytest.mark.asyncio
    async def test_completes_pipeline_when_no_next_phase(self, pipeline_mocks):
        phase = _make_phase(PhaseType.EXTRACTION)
        artifact = _make_artifact()
        todo = _make_todo()
        svc = _make_svc(
            current_phase=phase, artifact=artifact, todo=todo, next_phase=None,
        )
        result = await svc.confirm_phase(uuid.uuid4(), PhaseType.EXTRACTION)
        assert result is phase
        assert todo.status == TodoStatus.DONE
        pipeline_mocks["extract_experience"].assert_awaited_once()
        pipeline_mocks["notify_github"].assert_awaited_once()


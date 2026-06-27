"""ImpactAnalyzer + 风险矩阵单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.review.impact_analyzer import (
    ImpactAnalyzer,
    assess_risk,
    risk_recommendation,
)
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.review.value_objects import ModelChangeScope, RiskLevel
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus

# ── Risk Matrix Tests ────────────────────────────────────


class TestAssessRisk:
    """风险矩阵全覆盖。"""

    def test_clarification_additive(self):
        assert assess_risk(PhaseType.CLARIFICATION, ModelChangeScope.ADDITIVE) == RiskLevel.NONE

    def test_clarification_breaking(self):
        assert assess_risk(PhaseType.CLARIFICATION, ModelChangeScope.BREAKING) == RiskLevel.LOW

    def test_architecture_structural(self):
        assert assess_risk(PhaseType.ARCHITECTURE, ModelChangeScope.STRUCTURAL) == RiskLevel.MEDIUM

    def test_architecture_breaking(self):
        assert assess_risk(PhaseType.ARCHITECTURE, ModelChangeScope.BREAKING) == RiskLevel.HIGH

    def test_development_additive(self):
        assert assess_risk(PhaseType.DEVELOPMENT, ModelChangeScope.ADDITIVE) == RiskLevel.LOW

    def test_development_structural(self):
        assert assess_risk(PhaseType.DEVELOPMENT, ModelChangeScope.STRUCTURAL) == RiskLevel.HIGH

    def test_development_breaking(self):
        assert assess_risk(PhaseType.DEVELOPMENT, ModelChangeScope.BREAKING) == RiskLevel.CRITICAL

    def test_testing_breaking(self):
        assert assess_risk(PhaseType.TESTING, ModelChangeScope.BREAKING) == RiskLevel.CRITICAL

    def test_deployment_structural(self):
        assert assess_risk(PhaseType.DEPLOYMENT, ModelChangeScope.STRUCTURAL) == RiskLevel.CRITICAL

    def test_extraction_additive(self):
        assert assess_risk(PhaseType.EXTRACTION, ModelChangeScope.ADDITIVE) == RiskLevel.NONE

    def test_none_phase(self):
        assert assess_risk(None, ModelChangeScope.BREAKING) == RiskLevel.LOW


class TestRiskRecommendation:
    def test_none(self):
        assert "安全" in risk_recommendation(RiskLevel.NONE)

    def test_critical(self):
        assert "阻断" in risk_recommendation(RiskLevel.CRITICAL)


# ── ImpactAnalyzer Tests ─────────────────────────────────


def _make_todo(
    project_id: uuid.UUID,
    title: str = "Test Todo",
    phase: PhaseType | None = PhaseType.DEVELOPMENT,
    status: TodoStatus = TodoStatus.ACTIVE,
) -> Todo:
    todo = Todo(title=title, project_id=project_id, status=status)
    if phase:
        todo.current_phase = phase
    return todo


def _make_artifact(
    todo_id: uuid.UUID,
    entities: list[str] | None = None,
) -> Artifact:
    content: dict = {}
    if entities:
        content["data_model"] = {
            "entities": [{"name": name, "fields": []} for name in entities]
        }
    return Artifact(
        todo_id=todo_id,
        artifact_type=ArtifactType.TECH_ARCHITECTURE,
        content=content,
    )


class TestImpactAnalyzer:
    @pytest.fixture
    def project_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def mock_repos(self):
        todo_repo = MagicMock()
        artifact_repo = MagicMock()
        return todo_repo, artifact_repo

    @pytest.mark.asyncio
    async def test_no_affected_aggregates(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)

        report = await analyzer.analyze(project_id, [], ModelChangeScope.ADDITIVE)
        assert len(report.items) == 0
        assert "无受影响" in report.summary

    @pytest.mark.asyncio
    async def test_no_active_todos(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        todo_repo.list_all = AsyncMock(return_value=([], 0))
        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)

        report = await analyzer.analyze(project_id, ["Order"], ModelChangeScope.STRUCTURAL)
        assert len(report.items) == 0
        assert "无进行中" in report.summary

    @pytest.mark.asyncio
    async def test_finds_impacted_todo(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        todo = _make_todo(project_id, "订单功能", PhaseType.DEVELOPMENT)
        art = _make_artifact(todo.id, ["Order", "OrderItem"])

        todo_repo.list_all = AsyncMock(return_value=([todo], 1))
        artifact_repo.list_by_todo_id = AsyncMock(return_value=[art])

        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)
        report = await analyzer.analyze(project_id, ["Order"], ModelChangeScope.STRUCTURAL)

        assert len(report.items) == 1
        assert report.items[0].todo_title == "订单功能"
        assert "Order" in report.items[0].affected_aggregates
        assert report.items[0].risk == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_skips_non_overlapping_todo(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        todo = _make_todo(project_id, "用户功能", PhaseType.DEVELOPMENT)
        art = _make_artifact(todo.id, ["User", "UserProfile"])

        todo_repo.list_all = AsyncMock(return_value=([todo], 1))
        artifact_repo.list_by_todo_id = AsyncMock(return_value=[art])

        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)
        report = await analyzer.analyze(project_id, ["Order"], ModelChangeScope.BREAKING)

        assert len(report.items) == 0

    @pytest.mark.asyncio
    async def test_sorts_by_risk_descending(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        todo1 = _make_todo(project_id, "早期需求", PhaseType.CLARIFICATION)
        todo2 = _make_todo(project_id, "开发中需求", PhaseType.DEVELOPMENT)
        art1 = _make_artifact(todo1.id, ["Order"])
        art2 = _make_artifact(todo2.id, ["Order"])

        todo_repo.list_all = AsyncMock(return_value=([todo1, todo2], 2))
        artifact_repo.list_by_todo_id = AsyncMock(
            side_effect=lambda tid: [art1] if tid == todo1.id else [art2]
        )

        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)
        report = await analyzer.analyze(project_id, ["Order"], ModelChangeScope.BREAKING)

        assert len(report.items) == 2
        assert report.items[0].risk >= report.items[1].risk

    @pytest.mark.asyncio
    async def test_filters_non_active_todos(self, project_id, mock_repos):
        todo_repo, artifact_repo = mock_repos
        active = _make_todo(project_id, "Active", PhaseType.DEVELOPMENT, TodoStatus.ACTIVE)
        done = _make_todo(project_id, "Done", PhaseType.DEVELOPMENT, TodoStatus.DONE)
        art = _make_artifact(active.id, ["Order"])

        todo_repo.list_all = AsyncMock(return_value=([active, done], 2))
        artifact_repo.list_by_todo_id = AsyncMock(return_value=[art])

        analyzer = ImpactAnalyzer(todo_repo, artifact_repo)
        report = await analyzer.analyze(project_id, ["Order"], ModelChangeScope.STRUCTURAL)

        # done 的 todo 不应该出现在结果中
        assert len(report.items) <= 1
        for item in report.items:
            assert item.todo_title != "Done"

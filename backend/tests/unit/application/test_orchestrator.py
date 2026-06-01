"""ModelUpgradeOrchestrator 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.review.orchestrator import ModelUpgradeOrchestrator, UpgradeResult
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.project.entity import Project
from arc.domain.review.entity import ReviewFeedback
from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
    UpgradeStrategy,
)
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus


def _make_project(model_version: int = 1) -> Project:
    p = Project(name="Test")
    p.domain_model = {
        "version": model_version,
        "aggregates": [{"name": "Order", "fields": ["id"]}],
    }
    return p


def _make_todo(project_id: uuid.UUID, phase: PhaseType = PhaseType.DEVELOPMENT) -> Todo:
    todo = Todo(title="Test Todo", project_id=project_id, status=TodoStatus.ACTIVE)
    todo.current_phase = phase
    return todo


def _make_feedback(project_id: uuid.UUID) -> ReviewFeedback:
    return ReviewFeedback(
        project_id=project_id,
        issue=ReviewIssue(
            severity=ReviewIssueSeverity.ERROR,
            category=ReviewIssueCategory.TACTICAL,
            title="t", detail="d", suggestion="s",
        ),
        scope=ModelChangeScope.STRUCTURAL,
    )


class TestExecuteBlock:
    @pytest.fixture
    def repos(self):
        project_repo = MagicMock()
        todo_repo = MagicMock()
        artifact_repo = MagicMock()
        feedback_repo = MagicMock()
        return project_repo, todo_repo, artifact_repo, feedback_repo

    @pytest.mark.asyncio
    async def test_suspends_high_risk_todos(self, repos):
        project_repo, todo_repo, artifact_repo, feedback_repo = repos
        project = _make_project(1)
        pid = project.id
        todo = _make_todo(pid, PhaseType.DEVELOPMENT)
        feedback = _make_feedback(pid)

        # 交付物引用 Order 聚合
        art = Artifact(todo_id=todo.id, artifact_type=ArtifactType.TECH_ARCHITECTURE,
                       content={"data_model": {"entities": [{"name": "Order"}]}})

        project_repo.get_by_id = AsyncMock(return_value=project)
        project_repo.update = AsyncMock()
        todo_repo.list_all = AsyncMock(return_value=([todo], 1))
        todo_repo.get_by_id = AsyncMock(return_value=todo)
        todo_repo.update = AsyncMock()
        artifact_repo.list_by_todo_id = AsyncMock(return_value=[art])
        feedback_repo.get_by_id = AsyncMock(return_value=feedback)
        feedback_repo.update = AsyncMock()

        orch = ModelUpgradeOrchestrator(project_repo, todo_repo, artifact_repo, feedback_repo)
        new_model = {"aggregates": [{"name": "Order", "fields": ["id", "total"]}]}

        result = await orch.execute(pid, [feedback.id], new_model, UpgradeStrategy.BLOCK)

        assert result.success is True
        assert result.strategy == UpgradeStrategy.BLOCK
        assert result.new_model_version == 2
        assert todo.id in result.suspended_todo_ids
        assert todo.status == TodoStatus.SUSPENDED

    @pytest.mark.asyncio
    async def test_project_not_found(self, repos):
        project_repo, todo_repo, artifact_repo, feedback_repo = repos
        project_repo.get_by_id = AsyncMock(return_value=None)

        orch = ModelUpgradeOrchestrator(project_repo, todo_repo, artifact_repo, feedback_repo)
        result = await orch.execute(uuid.uuid4(), [], {}, UpgradeStrategy.BLOCK)

        assert result.success is False
        assert "不存在" in result.error


class TestExecuteDefer:
    @pytest.mark.asyncio
    async def test_defers_feedbacks(self):
        feedback_repo = MagicMock()
        fb = _make_feedback(uuid.uuid4())
        feedback_repo.get_by_id = AsyncMock(return_value=fb)
        feedback_repo.update = AsyncMock()

        orch = ModelUpgradeOrchestrator(MagicMock(), MagicMock(), MagicMock(), feedback_repo)
        result = await orch.execute(uuid.uuid4(), [fb.id], {}, UpgradeStrategy.DEFER)

        assert result.success is True
        assert result.strategy == UpgradeStrategy.DEFER
        assert fb.id in result.deferred_feedback_ids
        assert fb.status == ReviewFeedbackStatus.DEFERRED


class TestExtractAffectedAggregates:
    def test_detects_added(self):
        old = {"aggregates": [{"name": "Order"}]}
        new = {"aggregates": [{"name": "Order"}, {"name": "Payment"}]}
        result = ModelUpgradeOrchestrator._extract_affected_aggregates(new, old)
        assert "Payment" in result

    def test_detects_removed(self):
        old = {"aggregates": [{"name": "Order"}, {"name": "Legacy"}]}
        new = {"aggregates": [{"name": "Order"}]}
        result = ModelUpgradeOrchestrator._extract_affected_aggregates(new, old)
        assert "Legacy" in result

    def test_detects_changed(self):
        old = {"aggregates": [{"name": "Order", "fields": ["id"]}]}
        new = {"aggregates": [{"name": "Order", "fields": ["id", "total"]}]}
        result = ModelUpgradeOrchestrator._extract_affected_aggregates(new, old)
        assert "Order" in result

    def test_no_change(self):
        model = {"aggregates": [{"name": "Order", "fields": ["id"]}]}
        result = ModelUpgradeOrchestrator._extract_affected_aggregates(model, model)
        assert len(result) == 0

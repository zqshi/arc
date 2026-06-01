"""ReviewService 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.review.service import ReviewService, _parse_issue
from arc.domain.review.entity import InvalidFeedbackTransitionError, ReviewFeedback
from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)


def _make_feedback(**overrides) -> ReviewFeedback:
    defaults = dict(
        project_id=uuid.uuid4(),
        issue=ReviewIssue(
            severity=ReviewIssueSeverity.WARNING,
            category=ReviewIssueCategory.TACTICAL,
            title="test",
            detail="detail",
            suggestion="suggestion",
        ),
        scope=ModelChangeScope.ADDITIVE,
    )
    return ReviewFeedback(**{**defaults, **overrides})


class TestParseIssue:
    def test_valid_issue(self):
        data = {
            "severity": "error",
            "category": "strategic",
            "title": "缺少限界上下文",
            "detail": "需划分",
            "suggestion": "建议划分",
        }
        issue = _parse_issue(data)
        assert issue.severity == ReviewIssueSeverity.ERROR
        assert issue.category == ReviewIssueCategory.STRATEGIC
        assert issue.title == "缺少限界上下文"

    def test_unknown_severity_defaults_to_info(self):
        data = {"severity": "unknown", "category": "naming", "title": "t", "detail": "d", "suggestion": "s"}
        issue = _parse_issue(data)
        assert issue.severity == ReviewIssueSeverity.INFO

    def test_unknown_category_defaults_to_completeness(self):
        data = {"severity": "error", "category": "bogus", "title": "t", "detail": "d", "suggestion": "s"}
        issue = _parse_issue(data)
        assert issue.category == ReviewIssueCategory.COMPLETENESS

    def test_missing_fields_default_to_empty(self):
        issue = _parse_issue({})
        assert issue.title == ""
        assert issue.detail == ""
        assert issue.suggestion == ""


class TestReviewServiceValidateAndPersist:
    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.create = AsyncMock(side_effect=lambda fb: fb)
        return repo

    @pytest.mark.asyncio
    async def test_no_issues_returns_empty(self, mock_repo):
        svc = ReviewService(mock_repo)
        with patch("arc.application.review.service.validate_domain_model", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"score": 90, "issues": [], "strengths": ["good"], "summary": "ok"}
            result = await svc.validate_and_persist(uuid.uuid4(), {"version": 1})

        assert result == []
        mock_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_feedbacks_from_issues(self, mock_repo):
        svc = ReviewService(mock_repo)
        issues = [
            {"severity": "error", "category": "strategic", "title": "issue1", "detail": "d1", "suggestion": "s1"},
            {"severity": "warning", "category": "naming", "title": "issue2", "detail": "d2", "suggestion": "s2"},
        ]
        with patch("arc.application.review.service.validate_domain_model", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"score": 50, "issues": issues}
            project_id = uuid.uuid4()
            result = await svc.validate_and_persist(project_id, {"version": 5})

        assert len(result) == 2
        assert mock_repo.create.call_count == 2

        # 第一个: strategic + error → breaking
        fb1 = result[0]
        assert fb1.scope == ModelChangeScope.BREAKING
        assert fb1.model_version == 5
        assert fb1.project_id == project_id

        # 第二个: naming → additive
        fb2 = result[1]
        assert fb2.scope == ModelChangeScope.ADDITIVE

    @pytest.mark.asyncio
    async def test_passes_source_todo_id(self, mock_repo):
        svc = ReviewService(mock_repo)
        todo_id = uuid.uuid4()
        issues = [{"severity": "info", "category": "completeness", "title": "t", "detail": "d", "suggestion": "s"}]
        with patch("arc.application.review.service.validate_domain_model", new_callable=AsyncMock) as mock_validate:
            mock_validate.return_value = {"score": 70, "issues": issues}
            result = await svc.validate_and_persist(uuid.uuid4(), {"version": 1}, source_todo_id=todo_id)

        assert result[0].source_todo_id == todo_id


class TestReviewServiceResolveFeedback:
    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.update = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_accept(self, mock_repo):
        fb = _make_feedback()
        mock_repo.get_by_id = AsyncMock(return_value=fb)
        svc = ReviewService(mock_repo)

        result = await svc.resolve_feedback(fb.id, "accept", "will upgrade")
        assert result.status == ReviewFeedbackStatus.ACCEPTED
        assert result.resolution_note == "will upgrade"
        mock_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_defer(self, mock_repo):
        fb = _make_feedback()
        mock_repo.get_by_id = AsyncMock(return_value=fb)
        svc = ReviewService(mock_repo)

        result = await svc.resolve_feedback(fb.id, "defer", "next version")
        assert result.status == ReviewFeedbackStatus.DEFERRED

    @pytest.mark.asyncio
    async def test_reject(self, mock_repo):
        fb = _make_feedback()
        mock_repo.get_by_id = AsyncMock(return_value=fb)
        svc = ReviewService(mock_repo)

        result = await svc.resolve_feedback(fb.id, "reject", "false positive")
        assert result.status == ReviewFeedbackStatus.REJECTED

    @pytest.mark.asyncio
    async def test_not_found_raises(self, mock_repo):
        mock_repo.get_by_id = AsyncMock(return_value=None)
        svc = ReviewService(mock_repo)

        with pytest.raises(ValueError, match="not found"):
            await svc.resolve_feedback(uuid.uuid4(), "accept")

    @pytest.mark.asyncio
    async def test_invalid_action_raises(self, mock_repo):
        fb = _make_feedback()
        mock_repo.get_by_id = AsyncMock(return_value=fb)
        svc = ReviewService(mock_repo)

        with pytest.raises(ValueError, match="Invalid action"):
            await svc.resolve_feedback(fb.id, "bogus")

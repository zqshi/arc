"""ReviewFeedback 实体单元测试。"""

import uuid
from datetime import UTC, datetime

import pytest

from arc.domain.review.entity import InvalidFeedbackTransitionError, ReviewFeedback
from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)


def _make_issue(**overrides) -> ReviewIssue:
    defaults = dict(
        severity=ReviewIssueSeverity.WARNING,
        category=ReviewIssueCategory.TACTICAL,
        title="测试问题",
        detail="详细说明",
        suggestion="改进建议",
    )
    return ReviewIssue(**{**defaults, **overrides})


def _make_feedback(**overrides) -> ReviewFeedback:
    defaults = dict(
        project_id=uuid.uuid4(),
        issue=_make_issue(),
        scope=ModelChangeScope.ADDITIVE,
    )
    return ReviewFeedback(**{**defaults, **overrides})


class TestReviewFeedbackCreation:
    def test_defaults(self):
        fb = _make_feedback()
        assert fb.status == ReviewFeedbackStatus.PENDING
        assert fb.resolved_at is None
        assert fb.resolution_note == ""
        assert fb.source_todo_id is None
        assert fb.model_version == 0
        assert isinstance(fb.id, uuid.UUID)
        assert isinstance(fb.created_at, datetime)

    def test_full_fields(self):
        todo_id = uuid.uuid4()
        fb = _make_feedback(
            source_todo_id=todo_id,
            model_version=3,
            scope=ModelChangeScope.BREAKING,
        )
        assert fb.source_todo_id == todo_id
        assert fb.model_version == 3
        assert fb.scope == ModelChangeScope.BREAKING


class TestReviewFeedbackTransitions:
    def test_accept_from_pending(self):
        fb = _make_feedback()
        fb.accept("将在 v3.1 升级")
        assert fb.status == ReviewFeedbackStatus.ACCEPTED
        assert fb.resolution_note == "将在 v3.1 升级"
        assert fb.resolved_at is not None

    def test_defer_from_pending(self):
        fb = _make_feedback()
        fb.defer("延迟到下版本")
        assert fb.status == ReviewFeedbackStatus.DEFERRED
        assert fb.resolved_at is not None

    def test_reject_from_pending(self):
        fb = _make_feedback()
        fb.reject("评审有误")
        assert fb.status == ReviewFeedbackStatus.REJECTED

    def test_accept_from_deferred(self):
        fb = _make_feedback()
        fb.defer()
        fb.accept("重新接受")
        assert fb.status == ReviewFeedbackStatus.ACCEPTED

    def test_reject_from_deferred(self):
        fb = _make_feedback()
        fb.defer()
        fb.reject("最终驳回")
        assert fb.status == ReviewFeedbackStatus.REJECTED

    def test_cannot_transition_from_accepted(self):
        fb = _make_feedback()
        fb.accept()
        with pytest.raises(InvalidFeedbackTransitionError):
            fb.defer()

    def test_cannot_transition_from_rejected(self):
        fb = _make_feedback()
        fb.reject()
        with pytest.raises(InvalidFeedbackTransitionError):
            fb.accept()

    def test_cannot_accept_twice(self):
        fb = _make_feedback()
        fb.accept()
        with pytest.raises(InvalidFeedbackTransitionError):
            fb.accept()


class TestReviewFeedbackProperties:
    def test_is_resolved_pending(self):
        fb = _make_feedback()
        assert fb.is_resolved is False

    def test_is_resolved_after_accept(self):
        fb = _make_feedback()
        fb.accept()
        assert fb.is_resolved is True

    def test_is_resolved_after_defer(self):
        fb = _make_feedback()
        fb.defer()
        assert fb.is_resolved is True

    def test_is_actionable_only_when_accepted(self):
        fb = _make_feedback()
        assert fb.is_actionable is False
        fb.accept()
        assert fb.is_actionable is True

    def test_deferred_is_not_actionable(self):
        fb = _make_feedback()
        fb.defer()
        assert fb.is_actionable is False

"""ReviewFeedback 值对象单元测试。"""

from arc.domain.review.value_objects import (
    VALID_FEEDBACK_TRANSITIONS,
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)


class TestReviewFeedbackStatus:
    def test_all_values(self):
        assert set(ReviewFeedbackStatus) == {"pending", "accepted", "deferred", "rejected"}

    def test_pending_can_transition_to_all_terminals(self):
        allowed = VALID_FEEDBACK_TRANSITIONS[ReviewFeedbackStatus.PENDING]
        assert ReviewFeedbackStatus.ACCEPTED in allowed
        assert ReviewFeedbackStatus.DEFERRED in allowed
        assert ReviewFeedbackStatus.REJECTED in allowed

    def test_accepted_is_terminal(self):
        assert VALID_FEEDBACK_TRANSITIONS[ReviewFeedbackStatus.ACCEPTED] == set()

    def test_rejected_is_terminal(self):
        assert VALID_FEEDBACK_TRANSITIONS[ReviewFeedbackStatus.REJECTED] == set()

    def test_deferred_can_reopen(self):
        allowed = VALID_FEEDBACK_TRANSITIONS[ReviewFeedbackStatus.DEFERRED]
        assert ReviewFeedbackStatus.ACCEPTED in allowed
        assert ReviewFeedbackStatus.REJECTED in allowed


class TestModelChangeScope:
    def test_all_values(self):
        assert set(ModelChangeScope) == {"additive", "structural", "breaking"}

    def test_ordering_semantics(self):
        """additive < structural < breaking in severity."""
        scopes = [ModelChangeScope.BREAKING, ModelChangeScope.ADDITIVE, ModelChangeScope.STRUCTURAL]
        ordered = sorted(scopes, key=lambda s: list(ModelChangeScope).index(s))
        assert ordered == [ModelChangeScope.ADDITIVE, ModelChangeScope.STRUCTURAL, ModelChangeScope.BREAKING]


class TestReviewIssue:
    def test_frozen(self):
        issue = ReviewIssue(
            severity=ReviewIssueSeverity.ERROR,
            category=ReviewIssueCategory.STRATEGIC,
            title="缺少限界上下文",
            detail="Order 聚合未划分上下文",
            suggestion="建议划分为订单上下文",
        )
        assert issue.title == "缺少限界上下文"
        try:
            issue.title = "modified"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_equality(self):
        args = dict(
            severity=ReviewIssueSeverity.WARNING,
            category=ReviewIssueCategory.NAMING,
            title="命名不规范",
            detail="UserInfo 应为 User",
            suggestion="重命名",
        )
        assert ReviewIssue(**args) == ReviewIssue(**args)

    def test_inequality(self):
        base = dict(
            severity=ReviewIssueSeverity.INFO,
            category=ReviewIssueCategory.COMPLETENESS,
            title="t",
            detail="d",
            suggestion="s",
        )
        a = ReviewIssue(**base)
        b = ReviewIssue(**{**base, "title": "different"})
        assert a != b


class TestReviewIssueSeverity:
    def test_all_values(self):
        assert set(ReviewIssueSeverity) == {"error", "warning", "info"}


class TestReviewIssueCategory:
    def test_all_values(self):
        assert set(ReviewIssueCategory) == {"strategic", "tactical", "naming", "completeness"}

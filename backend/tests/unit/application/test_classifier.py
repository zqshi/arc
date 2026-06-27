"""变更分级分类器单元测试。"""


from arc.application.review.classifier import classify_change_scope
from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)


class TestClassifyChangeScope:
    """分级规则覆盖 category × severity 全矩阵。"""

    # -- naming: 任何 severity 都是 additive --

    def test_naming_error(self):
        assert classify_change_scope(ReviewIssueCategory.NAMING, ReviewIssueSeverity.ERROR) == ModelChangeScope.ADDITIVE

    def test_naming_warning(self):
        assert classify_change_scope(ReviewIssueCategory.NAMING, ReviewIssueSeverity.WARNING) == ModelChangeScope.ADDITIVE

    def test_naming_info(self):
        assert classify_change_scope(ReviewIssueCategory.NAMING, ReviewIssueSeverity.INFO) == ModelChangeScope.ADDITIVE

    # -- completeness --

    def test_completeness_info(self):
        assert classify_change_scope(ReviewIssueCategory.COMPLETENESS, ReviewIssueSeverity.INFO) == ModelChangeScope.ADDITIVE

    def test_completeness_warning(self):
        assert classify_change_scope(ReviewIssueCategory.COMPLETENESS, ReviewIssueSeverity.WARNING) == ModelChangeScope.ADDITIVE

    def test_completeness_error(self):
        assert classify_change_scope(ReviewIssueCategory.COMPLETENESS, ReviewIssueSeverity.ERROR) == ModelChangeScope.STRUCTURAL

    # -- tactical --

    def test_tactical_info(self):
        assert classify_change_scope(ReviewIssueCategory.TACTICAL, ReviewIssueSeverity.INFO) == ModelChangeScope.ADDITIVE

    def test_tactical_warning(self):
        assert classify_change_scope(ReviewIssueCategory.TACTICAL, ReviewIssueSeverity.WARNING) == ModelChangeScope.ADDITIVE

    def test_tactical_error(self):
        assert classify_change_scope(ReviewIssueCategory.TACTICAL, ReviewIssueSeverity.ERROR) == ModelChangeScope.STRUCTURAL

    # -- strategic --

    def test_strategic_info(self):
        assert classify_change_scope(ReviewIssueCategory.STRATEGIC, ReviewIssueSeverity.INFO) == ModelChangeScope.ADDITIVE

    def test_strategic_warning(self):
        assert classify_change_scope(ReviewIssueCategory.STRATEGIC, ReviewIssueSeverity.WARNING) == ModelChangeScope.ADDITIVE

    def test_strategic_error(self):
        assert classify_change_scope(ReviewIssueCategory.STRATEGIC, ReviewIssueSeverity.ERROR) == ModelChangeScope.BREAKING

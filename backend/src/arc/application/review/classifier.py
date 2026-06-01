"""评审反馈变更分级分类器。

基于确定性规则将 Validator 产出的 issue 映射到 ModelChangeScope，
不依赖 LLM。

分级规则:
| category     | severity | → scope      |
|-------------|----------|--------------|
| naming      | any      | additive     |
| completeness| info/warn| additive     |
| completeness| error    | structural   |
| tactical    | info/warn| additive     |
| tactical    | error    | structural   |
| strategic   | info     | additive     |
| strategic   | warning  | additive     |
| strategic   | error    | breaking     |
"""

from __future__ import annotations

from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)


def classify_change_scope(
    category: ReviewIssueCategory,
    severity: ReviewIssueSeverity,
) -> ModelChangeScope:
    """根据 issue 的 category 和 severity 确定变更分级。"""

    if category == ReviewIssueCategory.NAMING:
        return ModelChangeScope.ADDITIVE

    if category == ReviewIssueCategory.COMPLETENESS:
        if severity == ReviewIssueSeverity.ERROR:
            return ModelChangeScope.STRUCTURAL
        return ModelChangeScope.ADDITIVE

    if category == ReviewIssueCategory.TACTICAL:
        if severity == ReviewIssueSeverity.ERROR:
            return ModelChangeScope.STRUCTURAL
        return ModelChangeScope.ADDITIVE

    if category == ReviewIssueCategory.STRATEGIC:
        if severity == ReviewIssueSeverity.ERROR:
            return ModelChangeScope.BREAKING
        return ModelChangeScope.ADDITIVE

    return ModelChangeScope.ADDITIVE

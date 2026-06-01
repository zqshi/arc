"""ReviewFeedback 值对象 — 评审反馈状态流转与变更分级。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReviewFeedbackStatus(StrEnum):
    """评审反馈处理状态。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"
    REJECTED = "rejected"


VALID_FEEDBACK_TRANSITIONS: dict[ReviewFeedbackStatus, set[ReviewFeedbackStatus]] = {
    ReviewFeedbackStatus.PENDING: {
        ReviewFeedbackStatus.ACCEPTED,
        ReviewFeedbackStatus.DEFERRED,
        ReviewFeedbackStatus.REJECTED,
    },
    ReviewFeedbackStatus.ACCEPTED: set(),
    ReviewFeedbackStatus.DEFERRED: {ReviewFeedbackStatus.ACCEPTED, ReviewFeedbackStatus.REJECTED},
    ReviewFeedbackStatus.REJECTED: set(),
}


class ModelChangeScope(StrEnum):
    """领域模型变更范围分级。

    - ADDITIVE: 新增字段/值对象/枚举，不改已有契约
    - STRUCTURAL: 聚合边界调整，接口签名可能变
    - BREAKING: 实体拆分/合并/核心语义变更
    """

    ADDITIVE = "additive"
    STRUCTURAL = "structural"
    BREAKING = "breaking"


class ReviewIssueSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewIssueCategory(StrEnum):
    STRATEGIC = "strategic"
    TACTICAL = "tactical"
    NAMING = "naming"
    COMPLETENESS = "completeness"


@dataclass(frozen=True)
class ReviewIssue:
    """评审问题值对象 — 单个评审发现的不可变记录。"""

    severity: ReviewIssueSeverity
    category: ReviewIssueCategory
    title: str
    detail: str
    suggestion: str

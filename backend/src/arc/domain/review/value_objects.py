"""ReviewFeedback 值对象 — 评审反馈状态流转与变更分级。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


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


# ── 影响分析值对象 (Phase 2) ─────────────────────────────


class RiskLevel(IntEnum):
    """影响风险等级。"""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class ImpactItem:
    """单个受影响的 Todo。"""

    todo_id: uuid.UUID
    todo_title: str
    current_phase: str
    affected_aggregates: tuple[str, ...]
    risk: RiskLevel
    recommendation: str


@dataclass(frozen=True)
class ImpactReport:
    """影响分析报告 — 不可变。"""

    project_id: uuid.UUID
    affected_aggregates: tuple[str, ...]
    change_scope: ModelChangeScope
    items: tuple[ImpactItem, ...] = ()
    summary: str = ""

    @property
    def max_risk(self) -> RiskLevel:
        if not self.items:
            return RiskLevel.NONE
        return max(item.risk for item in self.items)

    @property
    def has_critical(self) -> bool:
        return any(item.risk >= RiskLevel.HIGH for item in self.items)

    @property
    def blocked_count(self) -> int:
        return sum(1 for item in self.items if item.risk >= RiskLevel.HIGH)


class UpgradeStrategy(StrEnum):
    """模型升级策略。"""

    BLOCK = "block"      # 暂停受影响需求，立即升级
    DEFER = "defer"      # 延迟到当前版本结束



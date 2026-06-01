"""ReviewFeedback 实体 — AI 评审反馈的领域模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.review.value_objects import (
    VALID_FEEDBACK_TRANSITIONS,
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
)


class InvalidFeedbackTransitionError(Exception):
    def __init__(self, current: ReviewFeedbackStatus, target: ReviewFeedbackStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition feedback from {current!r} to {target!r}")


@dataclass
class ReviewFeedback:
    """AI 评审产出的单条反馈。

    一条 ReviewFeedback 对应 Validator 产出的一个 issue，
    带有变更分级和状态流转能力。
    """

    project_id: uuid.UUID
    issue: ReviewIssue
    scope: ModelChangeScope
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_todo_id: uuid.UUID | None = None
    model_version: int = 0
    status: ReviewFeedbackStatus = ReviewFeedbackStatus.PENDING
    resolution_note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None

    def _transition_to(self, target: ReviewFeedbackStatus) -> None:
        allowed = VALID_FEEDBACK_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidFeedbackTransitionError(self.status, target)
        self.status = target

    def accept(self, note: str = "") -> None:
        """接受反馈，标记为需要升级。"""
        self._transition_to(ReviewFeedbackStatus.ACCEPTED)
        self.resolution_note = note
        self.resolved_at = datetime.now(UTC)

    def defer(self, note: str = "") -> None:
        """延迟到下一版本处理。"""
        self._transition_to(ReviewFeedbackStatus.DEFERRED)
        self.resolution_note = note
        self.resolved_at = datetime.now(UTC)

    def reject(self, note: str = "") -> None:
        """驳回反馈（评审有误或不适用）。"""
        self._transition_to(ReviewFeedbackStatus.REJECTED)
        self.resolution_note = note
        self.resolved_at = datetime.now(UTC)

    @property
    def is_resolved(self) -> bool:
        return self.status != ReviewFeedbackStatus.PENDING

    @property
    def is_actionable(self) -> bool:
        """是否需要后续升级动作。"""
        return self.status == ReviewFeedbackStatus.ACCEPTED

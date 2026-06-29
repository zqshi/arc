from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.value_objects import VALID_TRANSITIONS, Tag, TodoStatus


class InvalidStatusTransitionError(Exception):
    def __init__(self, current: TodoStatus, target: TodoStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current!r} to {target!r}")


@dataclass
class Todo:
    title: str
    description: str = ""
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    project_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    status: TodoStatus = TodoStatus.PENDING
    priority: int = 2
    current_phase: PhaseType | None = None
    tags: list[Tag] = field(default_factory=list)
    error_reason: str = ""
    suspended_reason: str = ""
    suspended_model_version: int | None = None
    source_session_id: uuid.UUID | None = None
    source_feature_key: str = ""
    github_issue_number: int | None = None
    github_pr_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_seen_at: datetime | None = None

    def _transition_to(self, target: TodoStatus) -> None:
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStatusTransitionError(self.status, target)
        self.status = target
        self.updated_at = datetime.now(UTC)

    def start_pipeline(self) -> None:
        if self.status != TodoStatus.PENDING:
            raise InvalidStatusTransitionError(self.status, TodoStatus.ACTIVE)
        self._transition_to(TodoStatus.ACTIVE)
        self.current_phase = PhaseType.CLARIFICATION

    def start_conversation(self) -> None:
        if self.status != TodoStatus.PENDING:
            raise InvalidStatusTransitionError(self.status, TodoStatus.ACTIVE)
        self._transition_to(TodoStatus.ACTIVE)
        self.current_phase = None

    def update_phase(self, phase: PhaseType) -> None:
        if self.status != TodoStatus.ACTIVE:
            raise InvalidStatusTransitionError(self.status, TodoStatus.ACTIVE)
        self.current_phase = phase
        self.updated_at = datetime.now(UTC)

    def complete(self) -> None:
        self._transition_to(TodoStatus.DONE)

    def force_complete(self) -> None:
        """强制完成 — 允许从 pending 直接到 done（跳过 active）。"""
        if self.status == TodoStatus.PENDING:
            self._transition_to(TodoStatus.ACTIVE)
        self._transition_to(TodoStatus.DONE)

    def reopen(self) -> None:
        """从 done/error 状态重新打开到 active/pending。"""
        if self.status == TodoStatus.ERROR:
            self._transition_to(TodoStatus.PENDING)
            self.current_phase = None
        elif self.status == TodoStatus.DONE:
            self._transition_to(TodoStatus.ACTIVE)
        else:
            raise InvalidStatusTransitionError(self.status, TodoStatus.ACTIVE)

    def mark_error(self, reason: str) -> None:
        if not reason or not reason.strip():
            raise ValueError("reason is required when marking error")
        self._transition_to(TodoStatus.ERROR)
        self.error_reason = reason

    def retry(self) -> None:
        self._transition_to(TodoStatus.PENDING)
        self.current_phase = None

    def abandon(self) -> None:
        self._transition_to(TodoStatus.ABANDONED)

    def suspend_for_upgrade(self, reason: str, model_version: int) -> None:
        """因领域模型升级暂停此需求。"""
        if not reason or not reason.strip():
            raise ValueError("reason is required when suspending")
        self._transition_to(TodoStatus.SUSPENDED)
        self.suspended_reason = reason
        self.suspended_model_version = model_version

    def resume_after_upgrade(self) -> None:
        """模型升级完成，恢复执行。仅允许从 SUSPENDED 状态调用。"""
        if self.status != TodoStatus.SUSPENDED:
            raise InvalidStatusTransitionError(self.status, TodoStatus.ACTIVE)
        self._transition_to(TodoStatus.ACTIVE)
        self.suspended_reason = ""
        self.suspended_model_version = None

    @property
    def is_suspended(self) -> bool:
        return self.status == TodoStatus.SUSPENDED

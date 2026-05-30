from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    VALID_VERSION_TRANSITIONS,
    ExecutionMode,
    ProjectStatus,
    VersionStatus,
)


@dataclass
class Project:
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    organization_id: uuid.UUID | None = None
    description: str = ""
    tech_stack: str = ""
    repo_url: str = ""
    local_path: str = ""
    conventions: str = ""
    codebase_summary: str = ""
    scan_fingerprint: str = ""
    scan_status: str = "idle"  # idle / scanning / completed / error
    scan_progress: str = ""
    scan_error: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    execution_mode: ExecutionMode = ExecutionMode.PIPELINE
    pipeline_config: dict = field(default_factory=lambda: dict(DEFAULT_PIPELINE_CONFIG))
    conversation_config: dict = field(default_factory=lambda: dict(DEFAULT_CONVERSATION_CONFIG))
    domain_model: dict = field(default_factory=dict)
    github_token: str = ""
    github_webhook_secret: str = ""
    github_config: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def archive(self) -> None:
        self.status = ProjectStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        self.status = ProjectStatus.ACTIVE
        self.updated_at = datetime.now(UTC)

    def soft_delete(self) -> None:
        """逻辑删除：标记为 deleted，保留数据。"""
        self.status = ProjectStatus.DELETED
        self.updated_at = datetime.now(UTC)

    def set_execution_mode(self, mode: ExecutionMode) -> None:
        self.execution_mode = mode
        self.updated_at = datetime.now(UTC)

    def update_pipeline_config(self, config: dict) -> None:
        self.pipeline_config = {**DEFAULT_PIPELINE_CONFIG, **config}
        self.updated_at = datetime.now(UTC)

    def update_conversation_config(self, config: dict) -> None:
        self.conversation_config = {**DEFAULT_CONVERSATION_CONFIG, **config}
        self.updated_at = datetime.now(UTC)

    def configure_github(self, token: str, owner: str, repo: str, webhook_secret: str) -> None:
        self.github_token = token
        self.github_webhook_secret = webhook_secret
        self.github_config = {"owner": owner, "repo": repo}
        self.updated_at = datetime.now(UTC)

    def disconnect_github(self) -> None:
        self.github_token = ""
        self.github_webhook_secret = ""
        self.github_config = {}
        self.updated_at = datetime.now(UTC)

    # -- Scan lifecycle --------------------------------------------------

    def start_scan(self) -> None:
        self.scan_status = "scanning"
        self.scan_progress = ""
        self.scan_error = ""
        self.updated_at = datetime.now(UTC)

    def update_scan_progress(self, stage: str) -> None:
        self.scan_progress = stage
        self.updated_at = datetime.now(UTC)

    def complete_scan(self, summary: str, fingerprint: str) -> None:
        self.scan_status = "completed"
        self.codebase_summary = summary
        self.scan_fingerprint = fingerprint
        self.scan_progress = ""
        self.updated_at = datetime.now(UTC)

    def fail_scan(self, error: str) -> None:
        self.scan_status = "error"
        self.scan_error = error
        self.scan_progress = ""
        self.updated_at = datetime.now(UTC)


@dataclass
class Version:
    project_id: uuid.UUID
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    goal: str = ""
    status: VersionStatus = VersionStatus.PLANNING
    parent_version_id: uuid.UUID | None = None
    order: int = 0
    changelog: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def activate(self) -> None:
        self._transition_to(VersionStatus.ACTIVE)

    def release(self) -> None:
        self._transition_to(VersionStatus.RELEASED)

    def replan(self) -> None:
        self._transition_to(VersionStatus.PLANNING)

    def set_changelog(self, summary: str) -> None:
        self.changelog = summary
        self.updated_at = datetime.now(UTC)

    def _transition_to(self, target: VersionStatus) -> None:
        allowed = VALID_VERSION_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise ValueError(f"Cannot transition version from {self.status!r} to {target!r}")
        self.status = target
        self.updated_at = datetime.now(UTC)

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    VALID_VERSION_TRANSITIONS,
    ExecutionMode,
    ModelChangeTrigger,
    ProcessConfig,
    ProcessConstraint,
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
    execution_mode: ExecutionMode = ExecutionMode.PIPELINE  # deprecated
    process_constraint: ProcessConstraint = ProcessConstraint.FREE
    process_config: ProcessConfig = field(default_factory=ProcessConfig)
    pipeline_config: dict = field(default_factory=lambda: dict(DEFAULT_PIPELINE_CONFIG))
    conversation_config: dict = field(default_factory=lambda: dict(DEFAULT_CONVERSATION_CONFIG))
    domain_model: dict = field(default_factory=dict)
    domain_model_history: list[dict] = field(default_factory=list)
    github_token: str = ""
    github_webhook_secret: str = ""
    github_config: dict = field(default_factory=dict)
    deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def archive(self) -> None:
        self.status = ProjectStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        self.status = ProjectStatus.ACTIVE
        self.updated_at = datetime.now(UTC)

    def soft_delete(self) -> None:
        """逻辑删除：标记为 deleted，记录时间戳，保留数据。"""
        self.status = ProjectStatus.DELETED
        self.deleted_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)

    def restore(self) -> None:
        """恢复逻辑删除的项目。"""
        self.status = ProjectStatus.ACTIVE
        self.deleted_at = None
        self.updated_at = datetime.now(UTC)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def set_execution_mode(self, mode: ExecutionMode) -> None:
        self.execution_mode = mode
        self.updated_at = datetime.now(UTC)

    def update_pipeline_config(self, config: dict) -> None:
        self.pipeline_config = {**DEFAULT_PIPELINE_CONFIG, **config}
        self.updated_at = datetime.now(UTC)

    def update_conversation_config(self, config: dict) -> None:
        base = {**DEFAULT_CONVERSATION_CONFIG, **(self.conversation_config or {})}
        for key, val in config.items():
            if isinstance(val, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **val}
            else:
                base[key] = val
        self.conversation_config = base
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

    # -- Domain model lifecycle -------------------------------------------

    def upgrade_domain_model(
        self,
        new_model: dict,
        trigger: ModelChangeTrigger,
        trigger_todo_id: str = "",
    ) -> int:
        """受控的领域模型升级 — 自动创建快照，递增版本号。

        Raises:
            ValueError: new_model 为空或无实质内容时拒绝升级。

        Returns:
            新的版本号。
        """
        if not new_model or (
            not new_model.get("aggregates")
            and not new_model.get("subdomains")
            and not new_model.get("contexts")
        ):
            raise ValueError("Cannot upgrade to an empty domain model")
        old_version = self.domain_model.get("version", 0)
        snapshot = {
            "version": old_version,
            "content": copy.deepcopy(self.domain_model),
            "trigger": trigger.value,
            "trigger_todo_id": trigger_todo_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.domain_model_history.append(snapshot)
        self.domain_model = new_model
        new_version = old_version + 1
        self.domain_model["version"] = new_version
        self.domain_model["updated_at"] = datetime.now(UTC).isoformat()
        self.updated_at = datetime.now(UTC)
        return new_version

    def rollback_domain_model(self, to_version: int) -> None:
        """回滚领域模型到指定版本。

        Raises:
            ValueError: 指定版本不存在于历史快照中。
        """
        for snap in reversed(self.domain_model_history):
            if snap["version"] == to_version:
                # 回滚本身也产生快照
                old_version = self.domain_model.get("version", 0)
                rollback_snapshot = {
                    "version": old_version,
                    "content": copy.deepcopy(self.domain_model),
                    "trigger": ModelChangeTrigger.ROLLBACK.value,
                    "trigger_todo_id": "",
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self.domain_model_history.append(rollback_snapshot)
                self.domain_model = copy.deepcopy(snap["content"])
                self.updated_at = datetime.now(UTC)
                return
        raise ValueError(f"Version {to_version} not found in domain model history")

    @property
    def domain_model_version(self) -> int:
        """当前领域模型版本号。"""
        return self.domain_model.get("version", 0)

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
    prototype_preview_url: str = ""
    deploy_url: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def set_prototype_preview_url(self, url: str) -> None:
        self.prototype_preview_url = url
        self.updated_at = datetime.now(UTC)

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

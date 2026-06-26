from __future__ import annotations

import copy
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.deployment.distributor import DistributorType
from arc.domain.deployment.signer import SignerType
from arc.domain.errors import DomainError
from arc.domain.project.charter import (
    ConventionTemplateProvider,
    ProjectCharter,
)
from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    VALID_PHASES,
    VALID_VERSION_TRANSITIONS,
    ContextPolicy,
    ExecutionMode,
    ModelChangeTrigger,
    ProcessConfig,
    ProcessConstraint,
    ProjectStatus,
    ProjectType,
    VersionStatus,
)


@dataclass
class Project:
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID | None = None  # 创建者 (v5.7.0: 模板提取 source_user_id)
    organization_id: uuid.UUID | None = None
    description: str = ""
    tech_stack: str = ""
    repo_url: str = ""
    local_path: str = ""
    conventions: str = ""
    # v6.3.0 — 项目宪章: 系统按 project_type 生成的意图驱动治理规范 (等价 CLAUDE.md)。
    # 与 conventions (用户补充) 并存分工, 同为 Project 内嵌字段层 (非独立 Artifact 记录)。
    charter: ProjectCharter | None = None
    codebase_summary: str = ""
    scan_fingerprint: str = ""
    scan_status: str = "idle"  # idle / scanning / completed / error
    scan_progress: str = ""
    scan_error: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE
    execution_mode: ExecutionMode = ExecutionMode.PIPELINE  # deprecated
    process_constraint: ProcessConstraint = ProcessConstraint.FREE
    project_type: ProjectType = ProjectType.STATIC_SITE
    process_config: ProcessConfig = field(default_factory=ProcessConfig)
    pipeline_config: dict = field(default_factory=lambda: dict(DEFAULT_PIPELINE_CONFIG))
    conversation_config: dict = field(default_factory=lambda: dict(DEFAULT_CONVERSATION_CONFIG))
    domain_model: dict = field(default_factory=dict)
    domain_model_history: list[dict] = field(default_factory=list)
    context_policy: ContextPolicy = field(default_factory=ContextPolicy)
    github_token: str = ""
    github_webhook_secret: str = ""
    github_config: dict = field(default_factory=dict)
    # 签名凭证 (v6.1.0) — 按平台分字段加密存储 (base64 Fernet token, 空=未配)
    # 加解密通过 set/get_signing_creds 回调注入, domain 不依赖 infrastructure/crypto
    enc_apple_creds: str = ""
    enc_win_creds: str = ""
    enc_android_creds: str = ""
    # 分发凭证 (v6.2.0) — 按渠道分字段加密存储 (与签名凭证独立)
    enc_appstore_creds: str = ""
    enc_playstore_creds: str = ""
    enc_tauri_updater_creds: str = ""
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
        """增量更新 pipeline_config — 以现有配置为 base 深度 merge, 不重置已有自定义。

        与 update_conversation_config 同构: dict 字段做 key 级 merge, 标量字段覆盖。
        v6.8.0 W3 修正: 旧实现 {**DEFAULT, **config} 为重置式, 部分更新会丢
        phase_capabilities 等已配字段。
        """
        base = {**DEFAULT_PIPELINE_CONFIG, **(self.pipeline_config or {})}
        for key, val in config.items():
            if isinstance(val, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **val}
            else:
                base[key] = val
        self.pipeline_config = base
        self.updated_at = datetime.now(UTC)

    def update_phase_capabilities(
        self, phase: str, capability_ids: list[str]
    ) -> None:
        """更新某环节启用的能力 (v6.8.0 W3)。

        结构性校验 phase ∈ 固定7阶段 + capability_ids 为 list;
        capability_id 存在性/active 由 application 层 (CapabilityService) 校验。
        """
        if phase not in VALID_PHASES:
            raise DomainError(
                f"非法环节: {phase} (合法: {sorted(VALID_PHASES)})"
            )
        if not isinstance(capability_ids, list):
            raise DomainError("capability_ids 必须为 list[str]")
        base = {**DEFAULT_PIPELINE_CONFIG, **(self.pipeline_config or {})}
        phase_caps = dict(base.get("phase_capabilities") or {})
        phase_caps[phase] = list(capability_ids)
        base["phase_capabilities"] = phase_caps
        self.pipeline_config = base
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

    # -- Signing credentials (v6.1.0) ------------------------------------

    def set_signing_creds(
        self,
        platform: SignerType,
        creds: dict,
        encrypt_fn,
    ) -> None:
        """加密存储某平台签名凭证。

        加解密函数注入 (application 层传 infrastructure/crypto 的 encrypt),
        避免 domain→infrastructure 违规。空 dict → 不存 (保持字段空)。
        """
        if not creds:
            return
        field_name = self._enc_field_for(platform)
        setattr(self, field_name, encrypt_fn(json.dumps(creds)))
        self.updated_at = datetime.now(UTC)

    def get_signing_creds(self, platform: SignerType, decrypt_fn) -> dict | None:
        """解密读取某平台凭证, 未配 (字段空) 返回 None。"""
        field_name = self._enc_field_for(platform)
        token = getattr(self, field_name) or ""
        if not token:
            return None
        plaintext = decrypt_fn(token)
        if not plaintext:
            return None
        try:
            return json.loads(plaintext)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _enc_field_for(platform: SignerType) -> str:
        """平台 → 加密字段名映射。"""
        return {
            SignerType.APPLE: "enc_apple_creds",
            SignerType.WINDOWS: "enc_win_creds",
            SignerType.ANDROID: "enc_android_creds",
        }[platform]

    # -- Distribution credentials (v6.2.0) -------------------------------

    def set_distribution_creds(
        self,
        channel: DistributorType,
        creds: dict,
        encrypt_fn,
    ) -> None:
        """加密存储某渠道分发凭证 (与签名凭证独立字段)。空 dict → 不存。"""
        if not creds:
            return
        field_name = self._dist_enc_field_for(channel)
        setattr(self, field_name, encrypt_fn(json.dumps(creds)))
        self.updated_at = datetime.now(UTC)

    def get_distribution_creds(self, channel: DistributorType, decrypt_fn) -> dict | None:
        """解密读取某渠道分发凭证, 未配返回 None。"""
        field_name = self._dist_enc_field_for(channel)
        token = getattr(self, field_name) or ""
        if not token:
            return None
        plaintext = decrypt_fn(token)
        if not plaintext:
            return None
        try:
            return json.loads(plaintext)
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def _dist_enc_field_for(channel: DistributorType) -> str:
        """渠道 → 分发凭证加密字段名映射。"""
        return {
            DistributorType.APP_STORE: "enc_appstore_creds",
            DistributorType.PLAY_STORE: "enc_playstore_creds",
            DistributorType.TAURI_UPDATER: "enc_tauri_updater_creds",
        }[channel]

    def update_context_policy(self, policy: ContextPolicy) -> None:
        """更新项目的上下文策略。"""
        self.context_policy = policy
        self.updated_at = datetime.now(UTC)

    # -- Charter lifecycle (v6.3.0) ---------------------------------------

    def initialize_charter(
        self, provider: ConventionTemplateProvider
    ) -> ProjectCharter:
        """按当前 project_type 从 provider 取模板, 初始化项目宪章。

        创建项目时由 workspace_service 调用 (注入 provider)。重复调用覆盖旧 charter
        (类型变更或模板升级时重新生成)。返回生成的 charter。
        """
        markdown = provider.get_template(self.project_type)
        self.charter = ProjectCharter(
            markdown=markdown,
            project_type=self.project_type,
            template_version=1,
            created_at=datetime.now(UTC),
        )
        self.updated_at = datetime.now(UTC)
        return self.charter

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

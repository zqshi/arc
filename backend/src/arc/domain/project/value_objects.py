from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ExecutionMode(StrEnum):
    """Deprecated — 使用 ProcessConstraint 代替。保留兼容旧数据。"""

    PIPELINE = "pipeline"
    CONVERSATION = "conversation"


class ProcessConstraint(StrEnum):
    """过程约束级别 — 控制门禁严格度和交付物管理方式。

    替代 ExecutionMode 的二分法，提供更细粒度的配置:
    - STRICT: 强制排序 + gate + 显式 confirm (原 pipeline)
    - MODERATE: 推荐顺序 + 宽松 gate + 可跳过
    - FREE: 无 phase 概念 + 自动提取 (原 conversation)
    """

    STRICT = "strict"
    MODERATE = "moderate"
    FREE = "free"


class GateStrictness(StrEnum):
    STRICT = "strict"
    MODERATE = "moderate"
    RELAXED = "relaxed"


class AgentAutonomy(StrEnum):
    FULL = "full"
    SUPERVISED = "supervised"


class WorkspaceType(StrEnum):
    """项目工作区类型 — 创建时选择。"""

    LOCAL = "local"          # 关联已有本地目录
    GITHUB = "github"        # 从 GitHub 克隆
    TEMPORARY = "temporary"  # 临时工作区（~/.arc/workspaces/{project_id}/）


class VersionStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    RELEASED = "released"


VALID_VERSION_TRANSITIONS: dict[VersionStatus, set[VersionStatus]] = {
    VersionStatus.PLANNING: {VersionStatus.ACTIVE},
    VersionStatus.ACTIVE: {VersionStatus.RELEASED, VersionStatus.PLANNING},
    VersionStatus.RELEASED: set(),
}


DEFAULT_PIPELINE_CONFIG: dict = {
    "enabled_phases": [
        "clarification",
        "ui_design",
        "architecture",
        "development",
        "testing",
        "deployment",
        "extraction",
    ],
    "required_phases": [
        "clarification",
        "ui_design",
        "architecture",
        "development",
        "testing",
        "deployment",
        "extraction",
    ],
    "gate_strictness": "strict",
    "auto_advance": False,
}

# 产品研发全量交付物 — 单一事实来源
#
# 三种模式的差异是交互方式（门禁/确认/展示），不是交付标准。
# 交付物全量一致，确保任何模式下项目都能形成闭环、高质量沉淀经验、构建模型。
#
# v5.5.0 起新增 app_code / service_spec:
# - app_code: DEVELOPMENT 阶段的机器可解析代码工程元数据 (Agent 写入, UI 只读)
# - service_spec: ARCHITECTURE 阶段的服务契约 (v5.6.0 BaaS 接入锚点)
REQUIRED_DELIVERABLES: list[str] = [
    "requirement_spec",
    "interaction_design",
    "ui_spec",
    "prototype",
    "tech_architecture",
    "service_spec",
    "dev_report",
    "app_code",
    "test_report",
    "deploy_report",
    "experience_card",
]

# 向后兼容 — 所有模式指向同一列表
STRICT_DELIVERABLES: list[str] = REQUIRED_DELIVERABLES
MODERATE_DELIVERABLES: list[str] = REQUIRED_DELIVERABLES
FREE_DELIVERABLES: list[str] = REQUIRED_DELIVERABLES

DELIVERABLES_BY_CONSTRAINT: dict[str, list[str]] = {
    "strict": REQUIRED_DELIVERABLES,
    "moderate": REQUIRED_DELIVERABLES,
    "free": REQUIRED_DELIVERABLES,
}

DEFAULT_CONVERSATION_CONFIG: dict = {
    "required_deliverables": REQUIRED_DELIVERABLES,
    "agent_autonomy": "supervised",
    "auto_archive": True,
    "loop_config": {
        "token_budget": 120000,
        "wall_timeout_seconds": 300,
        "max_tokens_per_call": 16384,
    },
    "git_sync": {
        "auto_commit": False,
        "auto_push": False,
        "commit_prefix": "feat",
        "target_branch": "",
    },
}


class ModelChangeTrigger(StrEnum):
    """触发领域模型变更的来源。"""

    EXTRACTOR = "extractor"
    MANUAL = "manual"
    UPGRADE = "upgrade"
    ROLLBACK = "rollback"


@dataclass(frozen=True)
class ProcessConfig:
    """过程配置 — 与 ProcessConstraint 配合使用。

    控制项目执行过程中的 gate 行为、交付物管理方式和前端展示。
    """

    constraint: ProcessConstraint = ProcessConstraint.FREE
    gate_strictness: GateStrictness = GateStrictness.MODERATE
    auto_extract: bool = True  # AI 回复后自动提取 deliverable
    require_explicit_confirm: bool = False  # 用户必须手动确认 deliverable
    show_phase_ui: bool = False  # 前端是否展示阶梯 UI

    @staticmethod
    def from_execution_mode(mode: ExecutionMode) -> "ProcessConfig":
        """从旧 ExecutionMode 迁移到新 ProcessConfig。"""
        if mode == ExecutionMode.PIPELINE:
            return ProcessConfig(
                constraint=ProcessConstraint.STRICT,
                gate_strictness=GateStrictness.STRICT,
                auto_extract=False,
                require_explicit_confirm=True,
                show_phase_ui=True,
            )
        return ProcessConfig(
            constraint=ProcessConstraint.FREE,
            gate_strictness=GateStrictness.MODERATE,
            auto_extract=True,
            require_explicit_confirm=False,
            show_phase_ui=False,
        )

    def to_dict(self) -> dict:
        return {
            "constraint": self.constraint.value,
            "gate_strictness": self.gate_strictness.value,
            "auto_extract": self.auto_extract,
            "require_explicit_confirm": self.require_explicit_confirm,
            "show_phase_ui": self.show_phase_ui,
        }

    @staticmethod
    def from_dict(data: dict) -> "ProcessConfig":
        if not data:
            return ProcessConfig()
        return ProcessConfig(
            constraint=ProcessConstraint(data.get("constraint", "free")),
            gate_strictness=GateStrictness(data.get("gate_strictness", "moderate")),
            auto_extract=data.get("auto_extract", True),
            require_explicit_confirm=data.get("require_explicit_confirm", False),
            show_phase_ui=data.get("show_phase_ui", False),
        )


@dataclass(frozen=True)
class DomainModelSnapshot:
    """领域模型不可变快照 — 变更前自动创建。

    记录变更前的完整模型内容，支持按版本号回滚。
    """

    version: int
    content: dict
    trigger: ModelChangeTrigger
    trigger_todo_id: str
    created_at: datetime


# ── 项目上下文策略 ─────────────────────────────────────────


class ExperienceIsolation(StrEnum):
    """经验隔离级别。"""

    PROJECT_ONLY = "project_only"      # 只注入本项目经验（默认，严格隔离）
    WITH_GLOBAL = "with_global"        # 本项目 + 全局标记的经验
    CROSS_PROJECT = "cross_project"    # 允许从其他项目借鉴（未来用）


# 所有可用的上下文 Provider source 标识
ALL_CONTEXT_PROVIDERS: list[str] = [
    "project",
    "domain_model",
    "review_feedback",
    "experience",
    "methodology",
    "code_capability",
    "deliverable",
    "sufficiency",
]


@dataclass(frozen=True)
class ContextPolicy:
    """项目级上下文策略 — 控制 AI 上下文的组装行为。

    每个项目独立配置，决定：
    - 启用哪些上下文来源（Provider）
    - 经验隔离级别
    - 各来源的 token 预算覆盖
    - 额外注入的自定义上下文片段
    """

    # 启用的 Provider 列表（默认全开）
    enabled_providers: tuple[str, ...] = tuple(ALL_CONTEXT_PROVIDERS)

    # 经验隔离级别
    experience_isolation: ExperienceIsolation = ExperienceIsolation.PROJECT_ONLY

    # Token 预算覆盖（phase → source → budget）
    # 例: {"architecture": {"domain_model": 12000}}
    budget_overrides: dict = None  # type: ignore[assignment]

    # 额外注入的静态上下文片段
    # 例: [{"content": "本项目使用 gRPC...", "priority": 1}]
    extra_segments: tuple[dict, ...] = ()

    def __post_init__(self):
        if self.budget_overrides is None:
            object.__setattr__(self, "budget_overrides", {})

    def is_provider_enabled(self, source: str) -> bool:
        return source in self.enabled_providers

    def get_budget_override(self, phase: str, source: str) -> int | None:
        """获取特定阶段+来源的 budget 覆盖值，None 表示使用默认。"""
        phase_overrides = self.budget_overrides.get(phase)
        if not phase_overrides:
            return None
        return phase_overrides.get(source)

    def to_dict(self) -> dict:
        return {
            "enabled_providers": list(self.enabled_providers),
            "experience_isolation": self.experience_isolation.value,
            "budget_overrides": self.budget_overrides or {},
            "extra_segments": list(self.extra_segments),
        }

    @staticmethod
    def from_dict(data: dict | None) -> "ContextPolicy":
        if not data:
            return ContextPolicy()
        try:
            return ContextPolicy(
                enabled_providers=tuple(
                    data.get("enabled_providers", ALL_CONTEXT_PROVIDERS)
                ),
                experience_isolation=ExperienceIsolation(
                    data.get("experience_isolation", "project_only")
                ),
                budget_overrides=data.get("budget_overrides", {}),
                extra_segments=tuple(data.get("extra_segments", [])),
            )
        except (ValueError, TypeError):
            return ContextPolicy()


# 默认策略 — 全开、项目隔离
DEFAULT_CONTEXT_POLICY = ContextPolicy()

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
        "architecture",
        "development",
        "testing",
        "extraction",
    ],
    "gate_strictness": "strict",
    "auto_advance": False,
}

DEFAULT_CONVERSATION_CONFIG: dict = {
    "required_deliverables": [
        "requirement_spec",
        "interaction_design",
        "ui_spec",
        "prototype",
        "tech_architecture",
        "dev_report",
        "test_report",
        "experience_card",
    ],
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

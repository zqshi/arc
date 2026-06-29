from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ProcessConstraint(StrEnum):
    """过程约束级别 — 控制门禁严格度和交付物管理方式。

    替代旧 pipeline/conversation 二分法，提供更细粒度的配置:
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


class ProjectType(StrEnum):
    """项目交付/部署形态 — 决定构建方式 + 产物形态 + 部署器。

    与 backend_type(后端形态) / app_code.framework(前端框架) 正交:
    - ProjectType 决定"怎么构建 + 部署到哪"
    - backend_type 决定"后端用啥" (none/supabase/embedded/external)
    - framework 决定"脚手架用啥" (react/vue/svelte/vanilla)

    新增类型时必须同步在 get_deployer() + PROTOTYPE_BUILD_GUIDES 三处注册,
    禁止在 service/prompt 里加 if project_type 分支。
    """

    STATIC_SITE = "static_site"  # 静态站点(官网/SPA) — v5.9.0 落地
    # 原生客户端(Tauri/Capacitor) — v6.0.0 激活, 聚焦容器可构建目标(linux/web/android apk)
    BINARY_APP = "binary_app"
    # 预留（后续版本激活时再加，避免触发死代码检测）:
    # BACKEND_SERVICE = "backend_service"  # 后端服务
    # CONTAINER = "container"            # 容器镜像
    # LIBRARY = "library"                 # 库/SDK


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
    # v6.8.0 W3 — 环节级能力配置: {phase: [capability_id(str)]}, 默认空=不注入。
    # 键为 VALID_PHASES (固定7阶段); CapabilityProvider 注入 + 门禁 capabilities_section 读取。
    "phase_capabilities": {},
}

# 固定7阶段合法键 (从 enabled_phases 派生, 单一事实来源) — 环节能力配置校验用。
VALID_PHASES = frozenset(DEFAULT_PIPELINE_CONFIG["enabled_phases"])

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

# v6.9: 按项目类型裁剪可见交付物 — 非app类不应显示 app_code/构建产物。
# 复用 charter/get_deployer 类型驱动注册表模式, 新增类型在此注册可见交付物。
# STATIC_SITE(静态站点): 无原生构建产物, 去掉 app_code(build 本不在 REQUIRED)
# BINARY_APP(原生客户端): 全量 + 构建产物 build(签名/分发锚点)
_BUILD_ONLY: frozenset[str] = frozenset({"build"})
DELIVERABLES_BY_TYPE: dict[ProjectType, frozenset[str]] = {
    ProjectType.STATIC_SITE: frozenset(REQUIRED_DELIVERABLES) - frozenset({"app_code"}),
    ProjectType.BINARY_APP: frozenset(REQUIRED_DELIVERABLES) | _BUILD_ONLY,
}


def deliverables_for_type(project_type: ProjectType) -> frozenset[str]:
    """返回该项目类型的可见交付物集合(未注册类型 fallback 全量)。"""
    return DELIVERABLES_BY_TYPE.get(project_type, frozenset(REQUIRED_DELIVERABLES))


def is_deliverable_visible(project_type: ProjectType, artifact_type: str) -> bool:
    """判断某交付物对该项目类型是否可见(环节显示/产出过滤用)。"""
    return artifact_type in deliverables_for_type(project_type)


# v6.9: 按项目类型裁剪可见阶段 — 当前两类型都全7阶段(差异在交付物, 非阶段),
# 为后续类型裁剪预留(如纯文档项目可裁剪 DEVELOPMENT)。新增类型在此注册。
PHASES_BY_TYPE: dict[ProjectType, frozenset[str]] = {
    ProjectType.STATIC_SITE: frozenset(DEFAULT_PIPELINE_CONFIG["enabled_phases"]),
    ProjectType.BINARY_APP: frozenset(DEFAULT_PIPELINE_CONFIG["enabled_phases"]),
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
    """过程配置 — constraint 的序列化容器。

    v6.15: 原 gate_strictness/auto_extract/require_explicit_confirm/show_phase_ui
    四字段前后端零业务消费 (gate 行为由 content.gate.GateProfile 接管, 提取/确认/
    UI 展示由 constraint + 链路决定), 已删除。容器保留以稳定 process_config 的
    DB/前后端契约, 仅持有 constraint。
    """

    constraint: ProcessConstraint = ProcessConstraint.FREE

    def to_dict(self) -> dict:
        return {"constraint": self.constraint.value}

    @staticmethod
    def from_dict(data: dict) -> "ProcessConfig":
        if not data:
            return ProcessConfig()
        return ProcessConfig(
            constraint=ProcessConstraint(data.get("constraint", "free")),
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
    "template",
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

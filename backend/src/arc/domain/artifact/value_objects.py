from __future__ import annotations

from enum import StrEnum

from arc.domain.deployment.signer import SignerType
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.sandbox.value_objects import BuildTarget


class ArtifactType(StrEnum):
    REQUIREMENT_SPEC = "requirement_spec"
    INTERACTION_DESIGN = "interaction_design"
    UI_SPEC = "ui_spec"
    PROTOTYPE = "prototype"
    TECH_ARCHITECTURE = "tech_architecture"
    DEV_REPORT = "dev_report"
    TEST_REPORT = "test_report"
    DEPLOY_REPORT = "deploy_report"
    EXPERIENCE_CARD = "experience_card"
    # v5.5.0 — DEVELOPMENT 阶段的机器可解析代码工程元数据
    APP_CODE = "app_code"
    # v5.5.0 — ARCHITECTURE 阶段的服务契约（BaaS 接入锚点）
    SERVICE_SPEC = "service_spec"
    # v6.9 — DEVELOPMENT 阶段的构建产物（builder runtime / 签名 / 分发锚点）
    BUILD = "build"
    # Legacy — kept for backward compat with existing DB records
    UI_DESIGN = "ui_design"


PHASE_ARTIFACT_MAP: dict[PhaseType, list[ArtifactType]] = {
    PhaseType.CLARIFICATION: [ArtifactType.REQUIREMENT_SPEC],
    PhaseType.UI_DESIGN: [
        ArtifactType.INTERACTION_DESIGN,
        ArtifactType.UI_SPEC,
        ArtifactType.PROTOTYPE,
    ],
    PhaseType.ARCHITECTURE: [ArtifactType.TECH_ARCHITECTURE, ArtifactType.SERVICE_SPEC],
    PhaseType.DEVELOPMENT: [ArtifactType.DEV_REPORT, ArtifactType.APP_CODE, ArtifactType.BUILD],
    PhaseType.TESTING: [ArtifactType.TEST_REPORT],
    PhaseType.DEPLOYMENT: [ArtifactType.DEPLOY_REPORT],
    PhaseType.EXTRACTION: [ArtifactType.EXPERIENCE_CARD],
}

# 向后兼容：返回每个 phase 的主交付物（第一个）
PHASE_PRIMARY_ARTIFACT: dict[PhaseType, ArtifactType] = {
    phase: artifacts[0] for phase, artifacts in PHASE_ARTIFACT_MAP.items()
}

ARTIFACT_LABELS: dict[ArtifactType, str] = {
    ArtifactType.REQUIREMENT_SPEC: "需求规格",
    ArtifactType.INTERACTION_DESIGN: "交互设计",
    ArtifactType.UI_SPEC: "视觉规范",
    ArtifactType.PROTOTYPE: "原型设计",
    ArtifactType.TECH_ARCHITECTURE: "技术架构",
    ArtifactType.DEV_REPORT: "开发报告",
    ArtifactType.TEST_REPORT: "测试报告",
    ArtifactType.DEPLOY_REPORT: "部署报告",
    ArtifactType.EXPERIENCE_CARD: "经验卡片",
    ArtifactType.APP_CODE: "应用代码",
    ArtifactType.SERVICE_SPEC: "服务契约",
    ArtifactType.BUILD: "构建产物",
    # Legacy
    ArtifactType.UI_DESIGN: "UI设计(旧)",
}

# 交付物必填字段定义 — 单一事实来源 (消除 agent_loop.py / chain.py 重复)
DELIVERABLE_REQUIRED_FIELDS: dict[str, list[str]] = {
    "requirement_spec": ["background", "user_stories", "acceptance_criteria", "boundaries"],
    "interaction_design": ["user_flows", "page_map"],
    "ui_spec": ["design_tokens", "component_specs"],
    "prototype": ["project_dir", "routes", "build_status"],
    "tech_architecture": ["data_model", "api_design", "tech_decisions"],
    "dev_report": ["test_design", "implementation", "validation"],
    "test_report": ["criteria_verification"],
    "deploy_report": ["deploy_log", "health_check_result", "build_evidence"],
    "experience_card": ["problem", "solution", "decisions"],
    # v5.5.0 — APP_CODE: 机器可解析的代码工程元数据 (Agent 写入, UI 只读)
    "app_code": ["project_dir", "tech_stack", "build_command", "run_command", "entry_points"],
    # v5.5.0 — SERVICE_SPEC: 服务契约 (v5.6.0 BaaS 接入锚点)
    "service_spec": ["data_model_ref", "data_persistence", "endpoints", "auth_strategy"],
    # v6.9 — BUILD: 构建产物 (builder/签名/分发锚点)
    # build_target=BuildTarget值, artifact_path=产物相对路径, build_status=success/failed
    # signature_status/distribution_status/product_path 预留 None (④接入时填)
    "build": ["build_target", "artifact_path", "build_status"],
}


# ---------------------------------------------------------------------------
# v6.19 T2 — 构建产物物理形态 (BuildArtifactKind) + 签名链路声明
# ---------------------------------------------------------------------------

# current.md T2 要点的"产物类型 .msi/.exe" 指此: 构建产物的物理文件形态,
# 与 ArtifactType (phase 维度的交付物锚点, 如 BUILD) 是两个维度 —— 一个 BUILD
# artifact 可含多种物理形态产物 (.msi + .exe)。
#
# 此前产物形态隐含在 DeployService._detect_sign_targets 的文件扩展名扫盘里
# (.exe→WINDOWS, .apk→ANDROID), T2 提升为 domain 显式真相源, T4 让签名路由读它
# (取代扩展名字符串匹配)。
#
# DELIVERABLES_BY_TYPE (domain/project/value_objects.py) 是 ProjectType→ArtifactType
# 交付物清单, 维度不同; Windows 不新增 ArtifactType (仍用 BUILD 锚点), 故该表无需
# 为 Windows 改 (current.md T2 要点把两者混述, 此处澄清)。

class BuildArtifactKind(StrEnum):
    """构建产物物理形态 — 决定签名平台 + 分发可见产物。

    与 BuildTarget ("构建到哪个目标") 正交: 一个 BuildTarget 产出多种形态
    (tauri_linux 产 .deb + .AppImage)。BuildTarget→形态集合见 TARGET_ARTIFACT_KINDS。
    """

    # 现有 target 产物 (linux 系, 无代码签名惯例)
    DEB = "deb"  # tauri_linux: .deb 包
    APPIMAGE = "appimage"  # tauri_linux: AppImage 单文件
    WEB_DIST = "web_dist"  # web: dist 静态资源 (不签名)
    APK = "apk"  # capacitor_apk: android apk

    # v6.19 T2: Windows 产物 (.msi/.exe, 走 SignerType.WINDOWS)。
    # TAURI_WINDOWS target 由 T3 加入后登记到 TARGET_ARTIFACT_KINDS。
    MSI = "msi"
    EXE = "exe"
    APP = "app"  # macOS bundle (.app 目录, APPLE codesign+notarytool) — 真相源完整性
    # iOS (.ipa, T5) / 鸿蒙 (.hap/.app, T8) 形态待对应 T5/T8 建模时加入。
    # 注: 鸿蒙 .app (App Pack, 文件) 与 mac .app (目录) 同扩展名, T8 用 is_dir 分流


# 物理形态 → 签名平台 (单一真相源)。
# 取代 DeployService._detect_sign_targets 的文件扩展名字符串匹配 (T4 接入)。
# None = 无签名需求 (Linux/web 产物无标准代码签名机制)。
# 全登记不变量: 每个 BuildArtifactKind 必须在此显式决策签名平台 (含 None 不签),
# 漏登记会导致 signer_for_kind 抛 KeyError (而非静默误判为不签)。
KIND_SIGNER_TYPE: dict[BuildArtifactKind, SignerType | None] = {
    BuildArtifactKind.DEB: None,
    BuildArtifactKind.APPIMAGE: None,
    BuildArtifactKind.WEB_DIST: None,
    BuildArtifactKind.APK: SignerType.ANDROID,
    # v6.19 T2: Windows 签名链路声明 (.msi/.exe → SignerType.WINDOWS, 复用 v6.1 signtool)
    BuildArtifactKind.MSI: SignerType.WINDOWS,
    BuildArtifactKind.EXE: SignerType.WINDOWS,
    BuildArtifactKind.APP: SignerType.APPLE,  # macOS bundle → codesign+notarytool (v6.1)
}


# BuildTarget → 产物形态集合 (单一真相源, T3 构建编排/产物建模读它)。
# 新增 BuildTarget 必须在此登记, 否则 target_artifact_kinds() 抛 ValueError
# (v6.15 硬不变量精神, 与 domain/sandbox/execution_backend.TARGET_BACKENDS 同构)。
# v6.19: 现有三 target 全登记; TAURI_WINDOWS (T3) / CAPACITOR_IOS (T6) /
# HARMONY_HAP (T9) 待对应 target 加入时登记 (须与 execution_backend.TARGET_BACKENDS
# 同步登记, 双真相源一致性由测试守护)。
TARGET_ARTIFACT_KINDS: dict[BuildTarget, frozenset[BuildArtifactKind]] = {
    BuildTarget.TAURI_LINUX: frozenset({BuildArtifactKind.DEB, BuildArtifactKind.APPIMAGE}),
    BuildTarget.WEB: frozenset({BuildArtifactKind.WEB_DIST}),
    BuildTarget.CAPACITOR_APK: frozenset({BuildArtifactKind.APK}),
    # v6.19 T3: Windows 产物 .msi + .exe (走 CI 编排, T2 已建模形态)
    BuildTarget.TAURI_WINDOWS: frozenset({BuildArtifactKind.MSI, BuildArtifactKind.EXE}),
}


def target_artifact_kinds(target: BuildTarget) -> frozenset[BuildArtifactKind]:
    """查询 target 的产物形态集合 (单一真相源)。

    新增 BuildTarget 漏登记时抛 ValueError, 强制同步 TARGET_ARTIFACT_KINDS —
    与 execution_backend.target_execution_backend 同构 (禁止只改 BuildTarget 枚举)。

    Raises:
        ValueError: target 未在 TARGET_ARTIFACT_KINDS 登记。
    """
    try:
        return TARGET_ARTIFACT_KINDS[target]
    except KeyError as exc:
        raise ValueError(
            f"BuildTarget {target} 未登记产物形态 — 新增 BuildTarget 必须在 "
            f"domain/artifact/value_objects.py TARGET_ARTIFACT_KINDS 显式登记, "
            f"禁止只改枚举不登记"
        ) from exc


def signer_for_kind(kind: BuildArtifactKind) -> SignerType | None:
    """查询产物形态对应的签名平台 (单一真相源, T4 签名路由读它)。

    None = 该形态无签名需求 (如 .deb / web dist)。全登记不变量: 未在
    KIND_SIGNER_TYPE 登记的形态抛 KeyError (而非静默返回 None 误判为不签)。
    """
    return KIND_SIGNER_TYPE[kind]


# 文件扩展名 → 物理形态 (单一真相源, DeployService._detect_sign_targets 读它 +
# signer_for_kind 决定签名平台)。T4 让 _detect_sign_targets 从扩展名硬编码改为
# 读本表 (消费 T2 真相源, 消除 KIND_SIGNER_TYPE 悬空)。
# .app 同扩展名歧义 (mac 目录 / 鸿蒙 App Pack 文件) — T4 按 mac 处理, T8 用 is_dir 分流。
EXTENSION_KIND: dict[str, BuildArtifactKind] = {
    ".msi": BuildArtifactKind.MSI,
    ".exe": BuildArtifactKind.EXE,
    ".apk": BuildArtifactKind.APK,
    ".app": BuildArtifactKind.APP,
    ".deb": BuildArtifactKind.DEB,
    ".appimage": BuildArtifactKind.APPIMAGE,
}

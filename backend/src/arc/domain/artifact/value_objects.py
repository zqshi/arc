from __future__ import annotations

from enum import StrEnum

from arc.domain.pipeline.value_objects import PhaseType


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
    PhaseType.DEVELOPMENT: [ArtifactType.DEV_REPORT, ArtifactType.APP_CODE],
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
    "deploy_report": ["deploy_log", "health_check_result"],
    "experience_card": ["problem", "solution", "decisions"],
    # v5.5.0 — APP_CODE: 机器可解析的代码工程元数据 (Agent 写入, UI 只读)
    "app_code": ["project_dir", "tech_stack", "build_command", "run_command", "entry_points"],
    # v5.5.0 — SERVICE_SPEC: 服务契约 (v5.6.0 BaaS 接入锚点)
    "service_spec": ["data_model_ref", "data_persistence", "endpoints", "auth_strategy"],
}

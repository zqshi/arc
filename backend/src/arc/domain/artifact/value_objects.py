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
    # Legacy — kept for backward compat with existing DB records
    UI_DESIGN = "ui_design"


PHASE_ARTIFACT_MAP: dict[PhaseType, ArtifactType] = {
    PhaseType.CLARIFICATION: ArtifactType.REQUIREMENT_SPEC,
    PhaseType.UI_DESIGN: ArtifactType.INTERACTION_DESIGN,
    PhaseType.ARCHITECTURE: ArtifactType.TECH_ARCHITECTURE,
    PhaseType.DEVELOPMENT: ArtifactType.DEV_REPORT,
    PhaseType.TESTING: ArtifactType.TEST_REPORT,
    PhaseType.DEPLOYMENT: ArtifactType.DEPLOY_REPORT,
    PhaseType.EXTRACTION: ArtifactType.EXPERIENCE_CARD,
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
    # Legacy
    ArtifactType.UI_DESIGN: "UI设计(旧)",
}

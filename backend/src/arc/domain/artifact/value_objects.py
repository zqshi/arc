from __future__ import annotations

from enum import StrEnum

from arc.domain.pipeline.value_objects import PhaseType


class ArtifactType(StrEnum):
    REQUIREMENT_SPEC = "requirement_spec"
    UI_DESIGN = "ui_design"
    TECH_ARCHITECTURE = "tech_architecture"
    DEV_REPORT = "dev_report"
    TEST_REPORT = "test_report"
    DEPLOY_REPORT = "deploy_report"
    EXPERIENCE_CARD = "experience_card"


PHASE_ARTIFACT_MAP: dict[PhaseType, ArtifactType] = {
    PhaseType.CLARIFICATION: ArtifactType.REQUIREMENT_SPEC,
    PhaseType.UI_DESIGN: ArtifactType.UI_DESIGN,
    PhaseType.ARCHITECTURE: ArtifactType.TECH_ARCHITECTURE,
    PhaseType.DEVELOPMENT: ArtifactType.DEV_REPORT,
    PhaseType.TESTING: ArtifactType.TEST_REPORT,
    PhaseType.DEPLOYMENT: ArtifactType.DEPLOY_REPORT,
    PhaseType.EXTRACTION: ArtifactType.EXPERIENCE_CARD,
}

ARTIFACT_LABELS: dict[ArtifactType, str] = {
    ArtifactType.REQUIREMENT_SPEC: "需求规格",
    ArtifactType.UI_DESIGN: "UI/UE设计方案",
    ArtifactType.TECH_ARCHITECTURE: "技术架构方案",
    ArtifactType.DEV_REPORT: "开发报告",
    ArtifactType.TEST_REPORT: "测试报告",
    ArtifactType.DEPLOY_REPORT: "部署报告",
    ArtifactType.EXPERIENCE_CARD: "经验卡片",
}

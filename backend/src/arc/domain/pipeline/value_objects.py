from __future__ import annotations

from enum import StrEnum


class PhaseType(StrEnum):
    CLARIFICATION = "clarification"
    UI_DESIGN = "ui_design"
    ARCHITECTURE = "architecture"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    EXTRACTION = "extraction"


PHASE_ORDER: dict[PhaseType, int] = {
    PhaseType.CLARIFICATION: 1,
    PhaseType.UI_DESIGN: 2,
    PhaseType.ARCHITECTURE: 3,
    PhaseType.DEVELOPMENT: 4,
    PhaseType.TESTING: 5,
    PhaseType.DEPLOYMENT: 6,
    PhaseType.EXTRACTION: 7,
}

PHASE_LABELS: dict[PhaseType, str] = {
    PhaseType.CLARIFICATION: "需求澄清",
    PhaseType.UI_DESIGN: "UI/UE设计",
    PhaseType.ARCHITECTURE: "技术架构",
    PhaseType.DEVELOPMENT: "开发实现",
    PhaseType.TESTING: "测试验证",
    PhaseType.DEPLOYMENT: "部署上线",
    PhaseType.EXTRACTION: "经验沉淀",
}


class PhaseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    AWAITING_CONFIRM = "awaiting_confirm"
    CONFIRMED = "confirmed"
    SKIPPED = "skipped"


VALID_PHASE_TRANSITIONS: dict[PhaseStatus, set[PhaseStatus]] = {
    PhaseStatus.PENDING: {PhaseStatus.ACTIVE, PhaseStatus.SKIPPED},
    PhaseStatus.ACTIVE: {PhaseStatus.AWAITING_CONFIRM},
    PhaseStatus.AWAITING_CONFIRM: {PhaseStatus.CONFIRMED, PhaseStatus.ACTIVE},
    PhaseStatus.CONFIRMED: {PhaseStatus.ACTIVE},  # rollback
    PhaseStatus.SKIPPED: {PhaseStatus.ACTIVE},     # un-skip
}


def next_phase(current: PhaseType) -> PhaseType | None:
    order = PHASE_ORDER[current]
    for pt, o in PHASE_ORDER.items():
        if o == order + 1:
            return pt
    return None

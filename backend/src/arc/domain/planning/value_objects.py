from __future__ import annotations

from enum import StrEnum


class PlanningStatus(StrEnum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    CONFIRMED = "confirmed"
    APPLIED = "applied"


VALID_PLANNING_TRANSITIONS: dict[PlanningStatus, set[PlanningStatus]] = {
    PlanningStatus.DRAFT: {PlanningStatus.REVIEWING},
    PlanningStatus.REVIEWING: {PlanningStatus.CONFIRMED, PlanningStatus.DRAFT},
    PlanningStatus.CONFIRMED: {PlanningStatus.APPLIED, PlanningStatus.DRAFT},
    PlanningStatus.APPLIED: {PlanningStatus.DRAFT},
}


class DocumentStatus(StrEnum):
    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class DeliverableStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PRODUCED = "produced"
    CONFIRMED = "confirmed"

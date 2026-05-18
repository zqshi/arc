from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class VersionStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    RELEASED = "released"


VALID_VERSION_TRANSITIONS: dict[VersionStatus, set[VersionStatus]] = {
    VersionStatus.PLANNING: {VersionStatus.ACTIVE},
    VersionStatus.ACTIVE: {VersionStatus.RELEASED, VersionStatus.PLANNING},
    VersionStatus.RELEASED: set(),
}

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ExecutionMode(StrEnum):
    PIPELINE = "pipeline"
    CONVERSATION = "conversation"


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
}

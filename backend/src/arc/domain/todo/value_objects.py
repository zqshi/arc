from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TodoStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DONE = "done"
    ERROR = "error"
    ABANDONED = "abandoned"


VALID_TRANSITIONS: dict[TodoStatus, set[TodoStatus]] = {
    TodoStatus.PENDING: {TodoStatus.ACTIVE, TodoStatus.ERROR, TodoStatus.ABANDONED},
    TodoStatus.ACTIVE: {TodoStatus.DONE, TodoStatus.ERROR, TodoStatus.ABANDONED, TodoStatus.SUSPENDED},
    TodoStatus.SUSPENDED: {TodoStatus.ACTIVE},
    TodoStatus.DONE: set(),
    TodoStatus.ERROR: {TodoStatus.PENDING},
    TodoStatus.ABANDONED: set(),
}


class ConversationPurpose(StrEnum):
    CLARIFICATION = "clarification"
    UI_DESIGN = "ui_design"
    ARCHITECTURE = "architecture"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    REVIEW = "review"
    UNIFIED = "unified"
    PLANNING = "planning"
    EXTRACTION = "extraction"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ExperienceScope(StrEnum):
    PERSONAL = "personal"
    PROJECT = "project"
    GLOBAL = "global"


class ExperienceStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    ARCHIVED = "archived"


class ExperienceCategory(StrEnum):
    TECHNICAL = "technical"
    BUSINESS_RULE = "business_rule"
    PITFALL = "pitfall"
    ARCHITECTURE_DECISION = "architecture_decision"
    SCOPE_CHANGE = "scope_change"
    ESTIMATION = "estimation"


class ExperienceSource(StrEnum):
    TODO_COMPLETION = "todo_completion"
    SCOPE_CHANGE = "scope_change"
    VERSION_RELEASE = "version_release"
    MANUAL = "manual"


@dataclass(frozen=True)
class Tag:
    label: str
    color: str

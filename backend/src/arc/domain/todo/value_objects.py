from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TodoStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"
    ERROR = "error"


VALID_TRANSITIONS: dict[TodoStatus, set[TodoStatus]] = {
    TodoStatus.PENDING: {TodoStatus.ACTIVE, TodoStatus.ERROR},
    TodoStatus.ACTIVE: {TodoStatus.DONE, TodoStatus.ERROR},
    TodoStatus.DONE: set(),
    TodoStatus.ERROR: {TodoStatus.PENDING},
}


class ConversationPurpose(StrEnum):
    CLARIFICATION = "clarification"
    UI_DESIGN = "ui_design"
    ARCHITECTURE = "architecture"
    DEVELOPMENT = "development"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    REVIEW = "review"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ExperienceScope(StrEnum):
    TODO = "todo"
    PROJECT = "project"
    GLOBAL = "global"


@dataclass(frozen=True)
class Tag:
    label: str
    color: str

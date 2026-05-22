from __future__ import annotations

from enum import StrEnum


class AgentType(StrEnum):
    OPENHANDS = "openhands"
    CODEX = "codex"
    CLAUDE_CODE = "claude_code"
    CURSOR = "cursor"


class SessionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


VALID_SESSION_TRANSITIONS: dict[SessionStatus, set[SessionStatus]] = {
    SessionStatus.PENDING: {SessionStatus.RUNNING, SessionStatus.CANCELLED},
    SessionStatus.RUNNING: {
        SessionStatus.PAUSED,
        SessionStatus.COMPLETED,
        SessionStatus.ERROR,
        SessionStatus.CANCELLED,
    },
    SessionStatus.PAUSED: {SessionStatus.RUNNING, SessionStatus.CANCELLED},
    SessionStatus.COMPLETED: set(),
    SessionStatus.ERROR: {SessionStatus.PENDING},
    SessionStatus.CANCELLED: set(),
}


AGENT_LABELS: dict[AgentType, str] = {
    AgentType.OPENHANDS: "OpenHands",
    AgentType.CODEX: "Codex",
    AgentType.CLAUDE_CODE: "Claude Code",
    AgentType.CURSOR: "Cursor",
}

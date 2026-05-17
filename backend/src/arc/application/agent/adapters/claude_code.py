"""Claude Code CLI adapter — skeleton for future implementation.

Claude Code runs as a local CLI process. This adapter will:
1. Spawn `claude` CLI with the task context as input
2. Monitor stdout/stderr for events
3. Report results back via the unified event model

The CLI wrapper approach allows Arc to orchestrate Claude Code as a
background process while the user interacts through the Arc UI.
"""

from __future__ import annotations

import logging

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent
from arc.domain.agent.value_objects import AgentType, SessionStatus

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter(CodingAgentAdapter):
    agent_type = AgentType.CLAUDE_CODE

    def __init__(self, cli_path: str = "claude", work_dir: str = "") -> None:
        self._cli_path = cli_path
        self._work_dir = work_dir

    async def start(self, context: TaskContext) -> str:
        raise NotImplementedError("Claude Code adapter not yet implemented")

    async def get_status(self, session_id: str) -> SessionStatus:
        raise NotImplementedError("Claude Code adapter not yet implemented")

    async def get_events(self, session_id: str, since: str = "") -> list[AgentEvent]:
        raise NotImplementedError("Claude Code adapter not yet implemented")

    async def cancel(self, session_id: str) -> None:
        raise NotImplementedError("Claude Code adapter not yet implemented")

    async def close(self) -> None:
        pass

"""Orchestration domain value objects.

Defines worker roles, subtask types, and statuses for the
Orchestrator-Worker multi-agent execution model.
"""

from __future__ import annotations

from enum import StrEnum


class WorkerRole(StrEnum):
    """Role of a participant in orchestrated execution."""

    ORCHESTRATOR = "orchestrator"  # Plans and synthesizes (main model)
    EXPLORER = "explorer"  # Read-only analysis (cheap model)
    WRITER = "writer"  # May write files (main model)
    SYNTHESIZER = "synthesizer"  # Aggregates worker outputs


class SubtaskType(StrEnum):
    """The kind of work a subtask performs."""

    READ_ANALYSIS = "read_analysis"  # Read files and analyze
    CODE_SEARCH = "code_search"  # Search for patterns
    FILE_WRITE = "file_write"  # Write or modify files
    COMMAND_EXEC = "command_exec"  # Execute shell commands
    SYNTHESIS = "synthesis"  # Combine results


class WorkerStatus(StrEnum):
    """Lifecycle status of a worker or subtask."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

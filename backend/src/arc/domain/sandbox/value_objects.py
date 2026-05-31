"""Sandbox domain value objects.

Defines the safety modes and policies for tool execution isolation.
Projects opt in to sandboxing via ``conversation_config["sandbox"]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SandboxMode(StrEnum):
    """How tool side-effects are isolated."""

    NONE = "none"  # Direct host execution (current default)
    APPROVAL_GATE = "approval_gate"  # Pause & ask user before mutating
    DOCKER = "docker"  # Execute inside a disposable container


@dataclass(frozen=True)
class SandboxPolicy:
    """Per-project sandbox configuration.

    Loaded from ``Project.conversation_config["sandbox"]``.
    When ``mode`` is NONE, all other fields are ignored.
    """

    mode: SandboxMode = SandboxMode.NONE

    # Docker-specific
    docker_image: str = "python:3.12-slim"
    timeout_seconds: int = 120
    memory_limit_mb: int = 512
    network_enabled: bool = False

    # Approval-gate-specific — which tools require user approval
    approval_required_for: list[str] = field(
        default_factory=lambda: ["write_file", "run_command"]
    )

    @classmethod
    def from_dict(cls, data: dict | None) -> SandboxPolicy:
        """Build a policy from a config dict (or return the default)."""
        if not data:
            return cls()
        mode_raw = data.get("mode", "none")
        try:
            mode = SandboxMode(mode_raw)
        except ValueError:
            mode = SandboxMode.NONE
        return cls(
            mode=mode,
            docker_image=data.get("docker_image", cls.docker_image),
            timeout_seconds=data.get("timeout_seconds", cls.timeout_seconds),
            memory_limit_mb=data.get("memory_limit_mb", cls.memory_limit_mb),
            network_enabled=data.get("network_enabled", cls.network_enabled),
            approval_required_for=data.get(
                "approval_required_for", ["write_file", "run_command"]
            ),
        )

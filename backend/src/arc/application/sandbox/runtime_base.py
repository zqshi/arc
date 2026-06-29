"""Sandbox runtime base contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

ToolImplFn = Callable[..., Awaitable[str]]


class SandboxRuntime(ABC):
    """Abstract interface for sandbox execution backends."""

    @abstractmethod
    async def run_command(self, params: dict) -> str:
        """Execute a shell command within the sandbox."""

    @abstractmethod
    async def write_file(self, params: dict) -> str:
        """Write a file within the sandbox."""

    async def close(self) -> None:
        """Release sandbox resources."""


"""Sandboxed tool registry — wraps ToolRegistry with sandbox isolation.

Replaces ``write_file`` and ``run_command`` handlers with sandboxed versions
that route through the configured SandboxRuntime (approval gate or Docker).
Read-only tools pass through unchanged.
"""

from __future__ import annotations

from arc.application.execution.tools import ToolDefinition, ToolRegistry
from arc.application.sandbox.runtime import SandboxRuntime


class SandboxedToolRegistry(ToolRegistry):
    """A ToolRegistry that routes mutation tools through a SandboxRuntime.

    Inherits all read-only tools from the parent ToolRegistry. Only
    ``write_file`` and ``run_command`` are overridden to use the sandbox.
    """

    def __init__(self, project_path: str, runtime: SandboxRuntime):
        super().__init__(project_path)
        self._runtime = runtime
        self._override_mutation_tools()

    def _override_mutation_tools(self) -> None:
        """Replace write_file and run_command with sandboxed handlers."""
        if "write_file" in self._tools:
            orig = self._tools["write_file"]
            self._tools["write_file"] = ToolDefinition(
                name=orig.name,
                description=orig.description + " [沙箱模式: 需要用户审批]",
                input_schema=orig.input_schema,
                handler=self._runtime.write_file,
            )

        if "run_command" in self._tools:
            orig = self._tools["run_command"]
            self._tools["run_command"] = ToolDefinition(
                name=orig.name,
                description=orig.description + " [沙箱模式: 需要用户审批]",
                input_schema=orig.input_schema,
                handler=self._runtime.run_command,
            )

    @property
    def runtime(self) -> SandboxRuntime:
        """Expose runtime for external lifecycle management."""
        return self._runtime

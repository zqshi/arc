"""Sandboxed tool registry — wraps ToolRegistry with sandbox isolation.

Replaces ``write_file`` and ``run_command`` handlers with sandboxed versions
that route through the configured SandboxRuntime (approval gate or Docker).
Read-only tools pass through unchanged — unless the runtime is a cloud
sandbox (OpenSandbox), where read tools also route through the sandbox to
keep file-system consistency (remote sandbox can't mount local project_path).
"""

from __future__ import annotations

from arc.application.execution.tools import ToolDefinition, ToolRegistry
from arc.application.sandbox.runtime_base import SandboxRuntime

# OpenSandbox 模式下需 override 的 read 类工具 (沙箱即工作区, 保证一致性)
_READ_TOOLS = ("read_file", "list_directory", "grep_search")


class SandboxedToolRegistry(ToolRegistry):
    """A ToolRegistry that routes mutation tools through a SandboxRuntime.

    Inherits all read-only tools from the parent ToolRegistry. Only
    ``write_file`` and ``run_command`` are overridden to use the sandbox —
    except for OpenSandbox (cloud) mode, where read tools also route through
    the sandbox runtime.
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

        # OpenSandbox (云沙箱即工作区): read 类也走沙箱, 保证一致性
        # (远程沙箱无法挂载本地 project_path, 本地 read 看不到沙箱写的文件)
        if hasattr(self._runtime, "read_file"):
            for name in _READ_TOOLS:
                orig = self._tools.get(name)
                if not orig:
                    continue
                handler = getattr(self._runtime, name, None)
                if handler is None:
                    continue
                self._tools[name] = ToolDefinition(
                    name=orig.name,
                    description=orig.description + " [云沙箱]",
                    input_schema=orig.input_schema,
                    handler=handler,
                )

    @property
    def runtime(self) -> SandboxRuntime:
        """Expose runtime for external lifecycle management."""
        return self._runtime

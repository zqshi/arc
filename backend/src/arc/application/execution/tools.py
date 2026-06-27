"""Tool definitions and registry for AI conversation tool-use.

Tools give the AI agent the ability to interact with the project codebase:
read files, list directories, search code, execute commands, and write files.

All file operations are sandboxed to the project's local_path.

文件操作 handler 的具体实现已拆分到 tool_fileops.py (沙箱化读写/搜索/执行, v6.11 T4);
本文件保留 tool 值对象 (ToolDefinition / ToolCall / ToolResult) 与 ToolRegistry 注册中心。
_run_command / _write_file 等 handler 经 re-export 保持原路径可达
(execution_engine 直接 `from arc.application.execution.tools import _run_command, _write_file`)。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from arc.application.execution.tool_fileops import (
    _grep_search,
    _list_directory,
    _read_file,
    _run_command,
    _write_file,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolDefinition:
    """A tool the AI can invoke during conversation."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict], Awaitable[str]]


@dataclass
class ToolCall:
    """A tool invocation from the LLM."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool."""

    tool_use_id: str
    content: str
    is_error: bool = False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Manages available tools for a specific project context."""

    def __init__(self, project_path: str):
        self._base_path = Path(project_path).expanduser().resolve()
        self._tools: dict[str, ToolDefinition] = {}
        self._register_defaults()

    def _register_defaults(self):
        bp = self._base_path

        self.register(ToolDefinition(
            name="read_file",
            description="读取项目中的文件内容。支持指定行范围。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                    "start_line": {
                        "type": "integer",
                        "description": "起始行号（从1开始），默认为1",
                        "default": 1,
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "结束行号，默认读取500行",
                    },
                },
                "required": ["path"],
            },
            handler=lambda p: _read_file(p, base_path=bp),
        ))

        self.register(ToolDefinition(
            name="write_file",
            description="创建或覆盖项目中的文件。自动创建父目录。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对于项目根目录的文件路径"},
                    "content": {"type": "string", "description": "文件内容"},
                },
                "required": ["path", "content"],
            },
            handler=lambda p: _write_file(p, base_path=bp),
        ))

        self.register(ToolDefinition(
            name="list_directory",
            description="列出项目目录结构。自动跳过 node_modules/.git 等目录。",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对于项目根目录的目录路径",
                        "default": ".",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "遍历深度，默认2",
                        "default": 2,
                    },
                },
                "required": [],
            },
            handler=lambda p: _list_directory(p, base_path=bp),
        ))

        self.register(ToolDefinition(
            name="grep_search",
            description="在项目中搜索文本或正则表达式，返回匹配的文件名和行号。",
            input_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索模式（支持正则表达式）",
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索范围（相对路径），默认整个项目",
                        "default": ".",
                    },
                    "include": {
                        "type": "string",
                        "description": "文件名过滤，如 '*.py' 或 '*.tsx'",
                    },
                },
                "required": ["pattern"],
            },
            handler=lambda p: _grep_search(p, base_path=bp),
        ))

        self.register(ToolDefinition(
            name="run_command",
            description=(
                "在项目根目录下执行 shell 命令。"
                "用于 git、npm、pytest、ls 等操作。超时最大300秒。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的 shell 命令"},
                    "timeout": {
                        "type": "integer",
                        "description": "超时秒数，默认30，最大300",
                        "default": 30,
                    },
                },
                "required": ["command"],
            },
            handler=lambda p: _run_command(p, base_path=bp),
        ))

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def register_baas_tools(self, *, project_id, baas_service) -> None:
        """注册 BaaS 相关 Agent tools (v5.6.0 T10)。

        Agent 在 DEVELOPMENT/ARCHITECTURE 阶段可通过这些 tools 直接操作 Supabase。
        需要调用方传入 baas_service (含 db 连接), 未传入则不注册 (向后兼容)。

        Tools:
        - supabase_provision: provision 项目 schema
        - supabase_execute_sql: 在项目 schema 内执行 SQL (Agent 直接操作 DB)
        - get_domain_model: introspect 当前 schema 领域结构
        """

        pid = project_id
        svc = baas_service

        async def _provision(params: dict) -> str:
            # 默认 dev URL (与 SupabaseClient 同库隔离约定一致)
            url = params.get("supabase_url") or "http://localhost:54321"
            instance = await svc.provision(
                project_id=pid,
                schema_name=f"arc_{pid.hex[:8]}",
                supabase_url=url,
            )
            return f"已 provision BaaS schema: {instance.schema_name}"

        async def _execute_sql(params: dict) -> str:
            # import 在 handler 内, 便于测试 patch (闭包不会锁定注册时的类对象)
            from arc.infrastructure.baas.supabase_client import SupabaseClient

            sql = params.get("sql", "")
            # 先 introspect 确认已 provision
            info = await svc.introspect(pid)
            schema = info.get("schema")
            if not schema or not info.get("exists"):
                return "错误: 项目未 provision BaaS, 请先调用 supabase_provision"
            client = SupabaseClient()
            try:
                result = await client.execute(sql, schema=schema)
                return f"执行成功: {result}"
            finally:
                await client.close()

        async def _get_domain_model(params: dict) -> str:
            info = await svc.introspect(pid)
            if not info.get("exists"):
                return "项目尚未 provision BaaS schema"
            return (
                f"schema: {info['schema']}\n"
                f"实体数: {info.get('entities_count', 0)}\n"
                f"状态数: {info.get('states_count', 0)}\n"
                f"跃迁数: {info.get('transitions_count', 0)}\n"
                f"权限策略数: {info.get('policies_count', 0)}"
            )

        self.register(ToolDefinition(
            name="supabase_provision",
            description=(
                "为当前项目 provision Supabase schema (创建独立 schema + 元模型表)。"
                "ARCHITECTURE 阶段领域模型确认后调用。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "supabase_url": {
                        "type": "string",
                        "description": "Supabase PostgREST endpoint, 留空用默认",
                    },
                },
                "required": [],
            },
            handler=_provision,
        ))

        self.register(ToolDefinition(
            name="supabase_execute_sql",
            description=(
                "在当前项目的 Supabase schema 内执行 SQL (建表/写 RLS/插数据)。"
                "自动 SET search_path 到项目 schema, 隔离其他项目数据。"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "要执行的 SQL 语句"},
                },
                "required": ["sql"],
            },
            handler=_execute_sql,
        ))

        self.register(ToolDefinition(
            name="get_domain_model",
            description=(
                "读取当前项目 Supabase schema 的领域结构概况 "
                "(实体/状态/跃迁/权限策略计数)。"
                "做增量变更前先了解当前结构。"
            ),
            input_schema={"type": "object", "properties": {}, "required": []},
            handler=_get_domain_model,
        ))

    def scoped(
        self,
        allowed_paths: list[str] | None = None,
        *,
        readonly: bool = False,
    ) -> "ToolRegistry":
        """Create a child registry with restricted scope.

        Used for context fencing in multi-agent mode. Workers can only
        access files within *allowed_paths* (relative to project root).

        Args:
            allowed_paths: Relative paths the child may access.  Empty or
                ``None`` means no extra restriction (full project access).
            readonly: If True, ``write_file`` and ``run_command`` are removed
                so the child registry can only read.
        """
        child = ToolRegistry.__new__(ToolRegistry)
        child._base_path = self._base_path
        child._tools = dict(self._tools)

        if readonly:
            child._tools.pop("write_file", None)
            child._tools.pop("run_command", None)

        if allowed_paths:
            resolved = [
                (self._base_path / p).resolve() for p in allowed_paths
            ]

            def _path_in_scope(params: dict) -> bool:
                rel = params.get("path", ".")
                target = (self._base_path / rel).resolve()
                return any(
                    target == r or r in target.parents or target in r.parents
                    for r in resolved
                )

            # Wrap file-reading tools with scope check
            for name in ("read_file", "list_directory", "grep_search"):
                original = child._tools.get(name)
                if not original:
                    continue

                def _make_scoped(orig_handler, tool_name):
                    async def _handler(p: dict) -> str:
                        if not _path_in_scope(p):
                            return "错误: 路径不在此 worker 的作用域内"
                        return await orig_handler(p)
                    return _handler

                child._tools[name] = ToolDefinition(
                    name=original.name,
                    description=original.description,
                    input_schema=original.input_schema,
                    handler=_make_scoped(original.handler, name),
                )

        return child

    @property
    def tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    async def execute(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if not tool:
            return ToolResult(
                tool_use_id=call.id,
                content=f"未知工具: {call.name}",
                is_error=True,
            )
        try:
            output = await tool.handler(call.input)
            return ToolResult(tool_use_id=call.id, content=output)
        except PermissionError as e:
            return ToolResult(tool_use_id=call.id, content=str(e), is_error=True)
        except Exception as e:
            logger.error("Tool %s execution failed: %s", call.name, e, exc_info=True)
            return ToolResult(
                tool_use_id=call.id,
                content=f"工具执行失败: {e}",
                is_error=True,
            )

    def to_anthropic_format(self) -> list[dict]:
        """Convert tools to Anthropic API format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def to_openai_format(self) -> list[dict]:
        """Convert tools to OpenAI function calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in self._tools.values()
        ]

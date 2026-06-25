"""Tool definitions and registry for AI conversation tool-use.

Tools give the AI agent the ability to interact with the project codebase:
read files, list directories, search code, execute commands, and write files.

All file operations are sandboxed to the project's local_path.

注: 本文件为 tool 注册中心, 行数超 500 行强限 (CLAUDE.md 例外)。
每个 ToolDefinition 是自包含注册块, 拆分会破坏注册聚合的可读性。
持续增长超 800 行时考虑按 tool 类别拆分子模块。
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

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
# Security: path sandboxing
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS = re.compile(
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f|"
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r|"
    r"mkfs|"
    r"dd\s+if=|"
    r":(){ :|:& };:|"
    r">\s*/dev/sd|"
    r"chmod\s+-R\s+777\s+/\s*$",
    re.IGNORECASE,
)


def _resolve_sandboxed_path(base: Path, relative: str) -> Path:
    """Resolve a path ensuring it stays within the sandbox base directory."""
    target = (base / relative).resolve()
    base_resolved = base.resolve()
    if not (target == base_resolved or base_resolved in target.parents):
        raise PermissionError(f"路径越界: {relative} 不在项目目录内")
    return target


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _read_file(params: dict, *, base_path: Path) -> str:
    path = _resolve_sandboxed_path(base_path, params["path"])
    if not path.is_file():
        return f"错误: 文件不存在 — {params['path']}"

    start_line = params.get("start_line", 1)
    end_line = params.get("end_line")
    max_lines = 500

    def _read():
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        s = max(0, start_line - 1)
        e = min(total, end_line) if end_line else min(s + max_lines, total)
        selected = lines[s:e]
        header = f"文件: {params['path']} ({total} 行, 显示 {s + 1}-{e})\n"
        numbered = "".join(f"{s + i + 1:4d} | {line}" for i, line in enumerate(selected))
        if e < total:
            numbered += f"\n... 还有 {total - e} 行未显示，使用 start_line={e + 1} 继续阅读"
        return header + numbered

    return await asyncio.to_thread(_read)


async def _write_file(params: dict, *, base_path: Path) -> str:
    path = _resolve_sandboxed_path(base_path, params["path"])

    def _write():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(params["content"])
        return f"已写入: {params['path']} ({len(params['content'])} 字符)"

    return await asyncio.to_thread(_write)


async def _list_directory(params: dict, *, base_path: Path) -> str:
    rel_path = params.get("path", ".")
    path = _resolve_sandboxed_path(base_path, rel_path)
    if not path.is_dir():
        return f"错误: 目录不存在 — {rel_path}"

    max_depth = params.get("max_depth", 2)
    max_entries = 200

    def _list():
        entries: list[str] = []

        def _walk(p: Path, depth: int, prefix: str):
            if depth > max_depth or len(entries) >= max_entries:
                return
            try:
                items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                entries.append(f"{prefix}[权限不足]")
                return
            for item in items:
                if item.name.startswith(".") and item.name not in (".env.example",):
                    continue
                if item.name in (
                    "node_modules", "__pycache__", ".git",
                    "dist", "build", ".venv", "venv",
                ):
                    continue
                if item.is_dir():
                    entries.append(f"{prefix}{item.name}/")
                    _walk(item, depth + 1, prefix + "  ")
                else:
                    size = item.stat().st_size
                    entries.append(f"{prefix}{item.name} ({_human_size(size)})")

        _walk(path, 0, "")
        header = f"目录: {rel_path} (深度 {max_depth})\n"
        if len(entries) >= max_entries:
            entries.append(f"... 已截断，共显示 {max_entries} 项")
        return header + "\n".join(entries)

    return await asyncio.to_thread(_list)


async def _grep_search(params: dict, *, base_path: Path) -> str:
    pattern = params["pattern"]
    search_path = params.get("path", ".")
    include = params.get("include", "")
    max_results = 50

    target = _resolve_sandboxed_path(base_path, search_path)
    if not target.exists():
        return f"错误: 路径不存在 — {search_path}"

    def _grep():
        cmd = ["grep", "-rn", "--color=never", "-I"]
        if include:
            cmd += ["--include", include]
        # Skip common non-source directories
        for skip in ("node_modules", ".git", "__pycache__", "dist", "build", ".venv"):
            cmd += ["--exclude-dir", skip]
        cmd += [pattern, str(target)]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
                cwd=str(base_path),
            )
        except subprocess.TimeoutExpired:
            return "搜索超时（15秒），请缩小搜索范围"

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        # Make paths relative to base_path
        rel_lines = []
        base_str = str(base_path) + "/"
        for line in lines[:max_results]:
            rel_lines.append(line.replace(base_str, ""))

        header = f"搜索 '{pattern}' "
        if include:
            header += f"(文件: {include}) "
        header += f"— {len(lines)} 处匹配"
        if len(lines) > max_results:
            header += f"（只显示前 {max_results} 条）"
        header += "\n"
        return header + "\n".join(rel_lines)

    return await asyncio.to_thread(_grep)


async def _run_command(params: dict, *, base_path: Path) -> str:
    command = params["command"]
    timeout = min(params.get("timeout", 30), 300)

    if _DANGEROUS_PATTERNS.search(command):
        return f"错误: 危险命令被拦截 — {command}"

    def _exec():
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(base_path),
                env={**os.environ, "HOME": os.environ.get("HOME", "")},
            )
            output_parts = []
            if result.stdout:
                stdout = result.stdout[:10000]
                if len(result.stdout) > 10000:
                    stdout += "\n... stdout 已截断 (超过 10000 字符)"
                output_parts.append(stdout)
            if result.stderr:
                stderr = result.stderr[:5000]
                if len(result.stderr) > 5000:
                    stderr += "\n... stderr 已截断"
                output_parts.append(f"[stderr]\n{stderr}")
            if result.returncode != 0:
                output_parts.append(f"[exit code: {result.returncode}]")
            return "\n".join(output_parts) if output_parts else "(无输出)"
        except subprocess.TimeoutExpired:
            return f"命令超时 ({timeout}秒): {command}"

    return await asyncio.to_thread(_exec)


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

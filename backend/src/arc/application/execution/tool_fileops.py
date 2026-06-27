"""沙箱化的文件操作工具实现 (从 tools.py 拆出, v6.11 T4)。

read_file / write_file / list_directory / grep_search / run_command 的具体 handler 实现,
全部沙箱化到项目 base_path 内, 供 ToolRegistry 注册为 tool handler。
其中 _run_command / _write_file 作为契约被 execution_engine 直接引用
(execution_engine.py 内 `from arc.application.execution.tools import _run_command, _write_file`,
经 tools.py re-export 保持原路径可达, 见 tools.py 顶部 import)。
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path

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
# Helpers
# ---------------------------------------------------------------------------


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"

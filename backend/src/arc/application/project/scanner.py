"""Codebase scanner — reads project structure and generates AI summary."""

from __future__ import annotations

import os
from pathlib import Path

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".tox", "coverage", ".cache",
    "vendor", "Pods", ".gradle", "out",
}

KEY_FILES = [
    "README.md", "README.rst", "README",
    "package.json", "pyproject.toml", "requirements.txt",
    "go.mod", "Cargo.toml", "pom.xml", "build.gradle",
    "Makefile", "CMakeLists.txt",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    ".env.example", "tsconfig.json",
]

MAX_FILE_CHARS = 6000
MAX_TREE_LINES = 200

SCAN_PROMPT = """你是一个代码库分析专家。请根据以下项目结构和关键文件内容，生成一份全面的项目概况分析。

## 要求输出（Markdown 格式）
1. **项目概述** — 一句话描述项目做什么
2. **技术栈** — 语言、框架、数据库、工具链
3. **项目结构** — 主要模块/目录的职责（表格形式）
4. **入口点** — 启动方式、主要命令
5. **架构模式** — 采用的设计模式（如 DDD、MVC、微服务等）
6. **当前状态** — 项目成熟度判断（早期/生产/维护）、是否有测试、CI/CD
7. **关键依赖** — 核心第三方库及用途

## 项目目录
{path}

## 目录树
```
{tree}
```

## 关键文件内容
{files_content}
"""


class CodebaseScanner:
    def __init__(self, path: str):
        self.root = Path(os.path.expanduser(path)).resolve()
        if not self.root.is_dir():
            raise ValueError(f"路径不存在或不是目录: {self.root}")

    def scan(self) -> dict:
        """Returns raw scan data: tree + key file contents."""
        tree = self._build_tree()
        files = self._read_key_files()
        return {"path": str(self.root), "tree": tree, "files": files}

    def build_prompt(self) -> str:
        data = self.scan()
        files_section = ""
        for fname, content in data["files"].items():
            files_section += f"\n### {fname}\n```\n{content}\n```\n"
        return SCAN_PROMPT.format(
            path=data["path"],
            tree=data["tree"],
            files_content=files_section or "(未找到关键文件)",
        )

    def _build_tree(self) -> str:
        lines: list[str] = []
        self._walk(self.root, "", lines, depth=0, max_depth=3)
        if len(lines) > MAX_TREE_LINES:
            lines = lines[:MAX_TREE_LINES]
            lines.append("... (已截断)")
        return "\n".join(lines)

    def _walk(self, directory: Path, prefix: str, lines: list[str], depth: int, max_depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in IGNORE_DIRS and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and not e.name.startswith(".")]

        items = dirs + files
        for i, entry in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                self._walk(entry, prefix + extension, lines, depth + 1, max_depth)

    def _read_key_files(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in KEY_FILES:
            fpath = self.root / name
            if fpath.is_file():
                try:
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    if len(content) > MAX_FILE_CHARS:
                        content = content[:MAX_FILE_CHARS] + "\n... (已截断)"
                    result[name] = content
                except (PermissionError, OSError):
                    continue
        return result


async def scan_and_summarize(path: str) -> str:
    """Convenience function: scan codebase and get LLM summary."""
    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.ai.resilience import create_resilient_adapter

    scanner = CodebaseScanner(path)
    prompt = scanner.build_prompt()

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.content
    finally:
        await adapter.close()

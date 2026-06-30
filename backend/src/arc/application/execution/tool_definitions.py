"""Tool 值对象定义 (从 tools.py 抽出, v6.19 质检 P1 循环依赖修复)。

原 tools.py 同时定义 ToolDefinition 与 ToolRegistry, build_tool.py 顶层 import
ToolDefinition (类型注解 + 构造实例), 而 tools.py 的 register_build_tool 函数内
延迟 import build_tool.make_build_tool → 构成 build_tool ↔ tools 模块环
(延迟导入规避了运行时崩溃, 但 AST 静态分析抓得到, 违反 CLAUDE.md 禁止循环依赖)。

解法: 把 Tool 值对象 (ToolDefinition / ToolCall / ToolResult) 抽到本独立模块,
build_tool 与 tools 都从此 import, 环即破 (build_tool 不再依赖 tools)。
tools.py 经 re-export 保持 `from arc.application.execution.tools import ToolDefinition`
原路径可达 (向后兼容, 同 v6.18 llm_adapter re-export 模式)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


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

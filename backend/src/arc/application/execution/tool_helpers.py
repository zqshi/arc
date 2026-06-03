"""工具循环辅助函数 — 从 tool_loop.py 提取的纯函数。

包含:
- build_output_preview: 结构化工具结果摘要
- build_anthropic_messages_with_tools: 构建含工具历史的 LLM 消息格式
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.execution.tools import ToolResult


def build_output_preview(tool_name: str, tool_input: dict, result: "ToolResult") -> str:
    """为不同工具类型生成结构化的 output_preview（供前端展示）。"""
    content = result.content
    if result.is_error:
        return content[:200]

    match tool_name:
        case "read_file":
            lines = content.count("\n") + 1
            path = tool_input.get("path", "")
            return f"{path} — {lines} lines, {len(content)} chars"
        case "write_file":
            path = tool_input.get("path", "")
            written = tool_input.get("content", "")
            return f"✓ {path} ({len(written.splitlines())} lines written)"
        case "run_command":
            lines = content.strip().splitlines()
            exit_info = ""
            if lines and "exit code" in lines[-1].lower():
                exit_info = lines[-1]
                lines = lines[:-1]
            preview_lines = lines[:3]
            preview = "\n".join(preview_lines)
            if len(lines) > 3:
                preview += f"\n... ({len(lines) - 3} more lines)"
            if exit_info:
                preview += f"\n{exit_info}"
            return preview[:300]
        case "grep_search":
            matches = content.count("\n") + (1 if content.strip() else 0)
            pattern = tool_input.get("pattern", "")
            return f'"{pattern}" — {matches} matches'
        case "list_directory":
            entries = content.count("\n")
            path = tool_input.get("path", ".")
            return f"{path}/ — {entries} entries"
        case _:
            return content[:200]


def build_anthropic_messages_with_tools(
    messages: list["LLMMessage"],
    tool_history: list[dict],
) -> tuple[str, list[dict]]:
    """Build Anthropic-format messages including tool call/result history."""
    system_parts: list[str] = []
    chat_msgs: list[dict] = []

    for m in messages:
        if m.role == "system":
            system_parts.append(m.content)
        else:
            chat_msgs.append({"role": m.role, "content": m.content})

    chat_msgs.extend(tool_history)

    return "\n\n".join(system_parts), chat_msgs

"""执行引擎辅助函数 — 从 execution_engine.py 提取的纯函数。

包含:
- _summarize_tool_input: 工具调用摘要生成
- _needs_user_input: 检测 AI 是否需要用户确认
- _map_tool_event: ToolLoopEvent → 前端 SSE dict 映射
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)


def summarize_tool_input(tool_name: str, tool_input: dict) -> str:
    """生成工具调用的简洁摘要（用于持久化到 metadata）。"""
    match tool_name:
        case "read_file":
            return tool_input.get("path", "")
        case "write_file":
            path = tool_input.get("path", "")
            content = tool_input.get("content", "")
            return f"{path} ({len(content.splitlines())} lines)"
        case "list_directory":
            return tool_input.get("path", ".")
        case "grep_search":
            return f'"{tool_input.get("pattern", "")}"'
        case "run_command":
            cmd = tool_input.get("command", "")
            return cmd[:80] + ("..." if len(cmd) > 80 else "")
        case _:
            return str(tool_input)[:60]


def needs_user_input(content: str) -> bool:
    """检测 AI 输出是否需要用户确认/澄清。"""
    if "[NEEDS_INPUT]" in content:
        return True
    last_paragraph = content.strip().split("\n\n")[-1] if content.strip() else ""
    question_indicators = ["？", "?", "你觉得", "你希望", "请确认", "你选择", "你倾向"]
    return any(ind in last_paragraph for ind in question_indicators)


def map_tool_event(event) -> list[dict]:
    """将 ToolLoopEvent 映射为前端 SSE 字典。"""
    results = []
    mid = event.metadata.get("message_id", str(uuid.uuid4()))

    if event.type == "text_delta":
        results.append({"message_id": mid, "content": event.content})
    elif event.type == "tool_call":
        results.append({
            "message_id": mid,
            "event": "tool_call",
            "tool_name": event.content,
            "tool_input": event.metadata.get("input", {}),
            "round": event.metadata.get("round", 0),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type == "tool_result":
        results.append({
            "message_id": mid,
            "event": "tool_result",
            "tool_name": event.metadata.get("tool_name", ""),
            "output_preview": event.content,
            "is_error": event.metadata.get("is_error", False),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type in ("orchestration_start", "synthesis_start", "orchestration_complete"):
        results.append({"event": event.type, **event.metadata})
    elif event.type in ("worker_start", "worker_complete", "worker_error"):
        results.append({"event": event.type, **event.metadata})
    elif event.type == "approval_required":
        results.append({"event": "approval_required", **event.metadata})
    elif event.type == "error":
        logger.error("Tool loop error: %s", event.content)
    elif event.type == "complete":
        logger.info(
            "Tool loop complete: %d rounds, %d tokens, %dms",
            event.metadata.get("tool_rounds", 0),
            event.metadata.get("total_tokens", 0),
            event.metadata.get("elapsed_ms", 0),
        )
        results.append({
            "event": "complete_metrics",
            "metrics": {
                "tool_rounds": event.metadata.get("tool_rounds", 0),
                "total_tokens": event.metadata.get("total_tokens", 0),
                "elapsed_ms": event.metadata.get("elapsed_ms", 0),
            },
        })
    return results

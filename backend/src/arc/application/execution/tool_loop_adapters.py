"""ToolLoop LLM provider 适配 (v5.8.0 从 tool_loop.py 拆分)。

Anthropic (native tool_use) 与 OpenAI (function calling) 的:
- 消息格式转换 (build_openai_messages)
- 响应解析 (parse_anthropic / parse_openai → ToolCall)
- usage token 提取

无状态纯函数, 由 ToolAwareLoop 调用。
"""
from __future__ import annotations

import json

from arc.application.ai.llm_adapter import LLMMessage
from arc.application.execution.tools import ToolCall


def build_openai_messages(
    base_messages: list[LLMMessage], tool_history: list[dict]
) -> list[dict]:
    """构建 OpenAI 格式消息 (含 tool_calls / tool 结果转换)。

    Anthropic tool_use/tool_result 格式 → OpenAI tool_calls/tool message。
    """
    formatted: list[dict] = []
    for m in base_messages:
        formatted.append({"role": m.role, "content": m.content})

    for msg in tool_history:
        if msg["role"] == "assistant":
            content_text = ""
            tool_calls_openai: list[dict] = []
            for block in msg["content"]:
                if block["type"] == "text":
                    content_text += block["text"]
                elif block["type"] == "tool_use":
                    tool_calls_openai.append({
                        "id": block["id"],
                        "type": "function",
                        "function": {
                            "name": block["name"],
                            "arguments": json.dumps(block["input"]),
                        },
                    })
            assistant_msg: dict = {"role": "assistant"}
            if content_text:
                assistant_msg["content"] = content_text
            if tool_calls_openai:
                assistant_msg["tool_calls"] = tool_calls_openai
            formatted.append(assistant_msg)

        elif msg["role"] == "user":
            for block in msg["content"]:
                if block["type"] == "tool_result":
                    formatted.append({
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    })

    return formatted


def parse_anthropic(response: dict) -> tuple[str, list[ToolCall]]:
    """解析 Anthropic 响应 → (text, tool_calls)。"""
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for block in response["content"]:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(
                id=block.id,
                name=block.name,
                input=block.input,
            ))

    return "\n".join(text_parts), tool_calls


def parse_openai(response: dict) -> tuple[str, list[ToolCall]]:
    """解析 OpenAI 响应 → (text, tool_calls)。"""
    message = response["message"]
    text = message.content or ""
    tool_calls: list[ToolCall] = []

    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                input_data = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                input_data = {"raw": tc.function.arguments}
            tool_calls.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                input=input_data,
            ))

    return text, tool_calls


def extract_usage_tokens(result: dict) -> int:
    """从 adapter.chat_with_tools 结果提取 token 用量 (input+output)。"""
    usage = result.get("usage", {})
    return usage.get("input", 0) + usage.get("output", 0)

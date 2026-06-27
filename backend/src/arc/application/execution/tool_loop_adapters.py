"""ToolLoop LLM provider 适配 (v5.8.0 从 tool_loop.py 拆分)。

Anthropic (native tool_use) 与 OpenAI (function calling) 的:
- 消息格式转换 (build_openai_messages)
- 响应解析 (parse_anthropic / parse_openai → ToolCall)
- usage token 提取

以及工具错误诊断 (v6.11 T4 从 tool_loop.py 迁入):
- ToolErrorDiagnosis 值对象 + from_llm 构造
- TOOL_ERROR_DIAGNOSIS_PROMPT 诊断 prompt 常量

无状态纯函数/值对象, 由 ToolAwareLoop 调用。
ToolErrorDiagnosis / TOOL_ERROR_DIAGNOSIS_PROMPT 经 tool_loop re-export 保持
`from arc.application.execution.tool_loop import ToolErrorDiagnosis` 路径可达。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

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


# ---------------------------------------------------------------------------
# Tool error diagnosis (v6.11 T4 从 tool_loop.py 迁入)
# ---------------------------------------------------------------------------

TOOL_ERROR_DIAGNOSIS_PROMPT = """诊断工具调用失败原因, 决定是否值得重试。

[上下文]
工具: {tool_name}
输入: {tool_input}
错误: {error}

[输出契约] 仅输出 JSON, 不要其他内容:
{{"should_retry": <bool>, "error_type": <str>, "reason": <str>}}

瞬时错误(超时/网络/限流)→should_retry=true; 永久错误(权限/参数/逻辑)→should_retry=false。
"""


@dataclass(frozen=True)
class ToolErrorDiagnosis:
    """LLM 工具错误诊断结果。"""

    should_retry: bool
    error_type: str
    reason: str = ""

    @classmethod
    def from_llm(cls, data: object) -> "ToolErrorDiagnosis | None":
        """从 LLM 输出构造。缺 should_retry 或非 dict → None (降级信号)。"""
        if not isinstance(data, dict) or "should_retry" not in data:
            return None
        return cls(
            should_retry=bool(data["should_retry"]),
            error_type=str(data.get("error_type", "unknown")),
            reason=str(data.get("reason", "")),
        )

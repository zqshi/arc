"""LLM 评审公共适配 — 复用 conversation_gate/sufficiency_gate 的 resilient adapter 模式。

供 drift_detector/error_loop_detector 等 execution 层 detector 复用,
避免各 detector 重复定义 _default_llm_review, 也避免调用方同时 import
两个同名函数需起别名 (触发 isort 拆分)。
"""

from __future__ import annotations

from arc.application.ai.json_extract import extract_json
from arc.application.ai.llm_adapter import LLMMessage
from arc.application.ai.resilience import create_resilient_adapter


async def default_llm_review(prompt: str) -> dict:
    """默认 LLM 评审: 调 resilient adapter, 返回解析后 JSON。

    失败由调用方捕获降级 (detector 内 try/except)。
    """
    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat([LLMMessage(role="user", content=prompt)])
    finally:
        await adapter.close()
    return extract_json(response.content)

"""Backward-compatible LLM adapter public module."""

from arc.application.ai.llm_factory import (
    create_llm_adapter,
    create_llm_adapter_from_config,
)
from arc.application.ai.llm_types import (
    LLMAdapter,
    LLMMessage,
    LLMResponse,
    StreamResult,
)

__all__ = [
    "LLMAdapter",
    "LLMMessage",
    "LLMResponse",
    "StreamResult",
    "create_llm_adapter",
    "create_llm_adapter_from_config",
]

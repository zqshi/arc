"""Application-layer AI/LLM services.

Public API:
    - LLM adapters: ``LLMAdapter``, ``OpenAIAdapter``, ``AnthropicAdapter``,
      ``LLMMessage``, ``LLMResponse``, ``create_llm_adapter``
    - OpenHands client: ``OpenHandsClient``, ``OpenHandsSession``,
      ``OpenHandsEvent``, ``OpenHandsSessionStatus``, ``create_openhands_client``
"""

from arc.application.ai.llm_adapter import (
    AnthropicAdapter,
    LLMAdapter,
    LLMMessage,
    LLMResponse,
    OpenAIAdapter,
    create_llm_adapter,
)
from arc.application.ai.openhands_client import (
    OpenHandsClient,
    OpenHandsError,
    OpenHandsEvent,
    OpenHandsSession,
    OpenHandsSessionStatus,
    create_openhands_client,
)

__all__ = [
    # LLM
    "LLMAdapter",
    "LLMMessage",
    "LLMResponse",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "create_llm_adapter",
    # OpenHands
    "OpenHandsClient",
    "OpenHandsError",
    "OpenHandsEvent",
    "OpenHandsSession",
    "OpenHandsSessionStatus",
    "create_openhands_client",
]

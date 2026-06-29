"""LLM adapter factory functions."""

from __future__ import annotations

from arc.application.ai.llm_types import LLMAdapter
from arc.domain.errors import AppError


def create_llm_adapter() -> LLMAdapter:
    """Create an adapter based on ``settings.llm_provider``."""
    from arc.config import settings

    provider = settings.llm_provider.lower()

    if provider == "openai":
        from arc.application.ai.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        from arc.application.ai.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
            embedding_api_key=settings.openai_api_key,
            embedding_base_url=settings.openai_base_url,
        )
    if provider == "deepseek":
        from arc.application.ai.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        )

    raise AppError(f"Unsupported LLM provider: {provider!r}")


def create_llm_adapter_from_config(llm_config: dict) -> LLMAdapter:
    """Create an adapter from project-level LLM configuration."""
    provider = (llm_config.get("provider") or "").lower()
    model = llm_config.get("model") or ""
    api_key = llm_config.get("api_key") or ""
    base_url = llm_config.get("base_url") or ""

    if not provider or not api_key:
        return create_llm_adapter()

    if provider in ("openai", "deepseek", "custom"):
        from arc.application.ai.openai_adapter import OpenAIAdapter

        default_base_url = (
            "https://api.deepseek.com/v1"
            if provider == "deepseek"
            else "https://api.openai.com/v1"
        )
        return OpenAIAdapter(
            api_key=api_key,
            model=model or "gpt-4o",
            base_url=base_url or default_base_url,
        )
    if provider == "anthropic":
        from arc.application.ai.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(
            api_key=api_key,
            model=model or "claude-sonnet-4-6",
            base_url=base_url or None,
        )

    return create_llm_adapter()

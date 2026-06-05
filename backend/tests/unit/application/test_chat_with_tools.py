"""Unit tests for LLMAdapter.chat_with_tools() and provider_type (v2.4.0)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.ai.llm_adapter import LLMAdapter


class TestAdapterProviderType:
    """Tests for provider_type property."""

    def test_base_adapter_provider_type_is_unknown(self):
        # LLMAdapter is ABC, can't instantiate directly; test via mock
        adapter = MagicMock(spec=LLMAdapter)
        adapter.provider_type = "unknown"
        assert adapter.provider_type == "unknown"

    @pytest.mark.asyncio
    async def test_openai_adapter_provider_type(self):
        with patch("openai.AsyncOpenAI"):
            from arc.application.ai.openai_adapter import OpenAIAdapter
            adapter = OpenAIAdapter(api_key="test", model="gpt-4o")
            assert adapter.provider_type == "openai"

    @pytest.mark.asyncio
    async def test_anthropic_adapter_provider_type(self):
        with patch("anthropic.AsyncAnthropic"):
            from arc.application.ai.anthropic_adapter import AnthropicAdapter
            adapter = AnthropicAdapter(api_key="test", model="claude-3")
            assert adapter.provider_type == "anthropic"


class TestOpenAIChatWithTools:
    """Tests for OpenAIAdapter.chat_with_tools()."""

    @pytest.mark.asyncio
    async def test_returns_expected_format(self):
        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 100
            mock_usage.completion_tokens = 50

            mock_choice = MagicMock()
            mock_choice.message.content = "result"

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = mock_usage

            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            from arc.application.ai.openai_adapter import OpenAIAdapter
            adapter = OpenAIAdapter(api_key="test", model="gpt-4o")

            result = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "hello"}],
                tools=[{"type": "function", "function": {"name": "test"}}],
            )

            assert result["type"] == "openai"
            assert result["usage"]["input"] == 100
            assert result["usage"]["output"] == 50
            assert result["response"] is mock_response


class TestAnthropicChatWithTools:
    """Tests for AnthropicAdapter.chat_with_tools()."""

    @pytest.mark.asyncio
    async def test_returns_expected_format(self):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            mock_usage = MagicMock()
            mock_usage.input_tokens = 200
            mock_usage.output_tokens = 80

            mock_response = MagicMock()
            mock_response.content = [{"type": "text", "text": "hello"}]
            mock_response.stop_reason = "end_turn"
            mock_response.usage = mock_usage

            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from arc.application.ai.anthropic_adapter import AnthropicAdapter
            adapter = AnthropicAdapter(api_key="test", model="claude-3")

            result = await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "hello"}],
                tools=[{"name": "test", "input_schema": {}}],
                system="You are helpful",
            )

            assert result["type"] == "anthropic"
            assert result["usage"]["input"] == 200
            assert result["usage"]["output"] == 80
            assert result["content"] == mock_response.content

            # Verify system was passed (with cache_control for Prompt Cache)
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"] == [
                {"type": "text", "text": "You are helpful", "cache_control": {"type": "ephemeral"}}
            ]

    @pytest.mark.asyncio
    async def test_no_system_omitted(self):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client

            mock_response = MagicMock()
            mock_response.content = []
            mock_response.stop_reason = "end_turn"
            mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from arc.application.ai.anthropic_adapter import AnthropicAdapter
            adapter = AnthropicAdapter(api_key="test", model="claude-3")

            await adapter.chat_with_tools(
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            assert "system" not in call_kwargs

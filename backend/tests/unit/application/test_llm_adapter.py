"""Unit tests for arc.application.ai.llm_adapter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.ai.anthropic_adapter import AnthropicAdapter
from arc.application.ai.llm_adapter import (
    LLMMessage,
    LLMResponse,
    create_llm_adapter,
)
from arc.application.ai.openai_adapter import OpenAIAdapter
from arc.domain.errors import AppError


class TestLLMMessage:
    def test_valid_roles(self) -> None:
        for role in ("system", "user", "assistant"):
            msg = LLMMessage(role=role, content="hello")
            assert msg.role == role

    def test_invalid_role_raises(self) -> None:
        with pytest.raises(AppError, match="Invalid role"):
            LLMMessage(role="tool", content="hello")

    def test_empty_content_raises(self) -> None:
        with pytest.raises(AppError, match="cannot be empty"):
            LLMMessage(role="user", content="")

    def test_whitespace_content_raises(self) -> None:
        with pytest.raises(AppError, match="cannot be empty"):
            LLMMessage(role="user", content="   ")

    def test_frozen(self) -> None:
        msg = LLMMessage(role="user", content="hi")
        with pytest.raises(AttributeError):
            msg.role = "system"  # type: ignore[misc]


class TestLLMResponse:
    def test_defaults(self) -> None:
        r = LLMResponse(content="ok", model="gpt-4o")
        assert r.usage == {}

    def test_with_usage(self) -> None:
        r = LLMResponse(
            content="ok", model="gpt-4o",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert r.usage["prompt_tokens"] == 10


class TestOpenAIAdapter:
    def test_requires_api_key(self) -> None:
        with pytest.raises(ValueError, match="api_key is required"):
            OpenAIAdapter(api_key="", model="gpt-4o")

    @patch("openai.AsyncOpenAI")
    async def test_chat_formats_messages(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        usage = SimpleNamespace(prompt_tokens=10, completion_tokens=20)
        choice = SimpleNamespace(message=SimpleNamespace(content="Hello!"))
        mock_response = SimpleNamespace(choices=[choice], model="gpt-4o", usage=usage)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        messages = [
            LLMMessage(role="system", content="You are helpful."),
            LLMMessage(role="user", content="Hi"),
        ]
        resp = await adapter.chat(messages, temperature=0.5)

        assert isinstance(resp, LLMResponse)
        assert resp.content == "Hello!"
        assert resp.model == "gpt-4o"
        assert resp.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    @patch("openai.AsyncOpenAI")
    async def test_chat_handles_none_content(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        choice = SimpleNamespace(message=SimpleNamespace(content=None))
        mock_response = SimpleNamespace(choices=[choice], model="gpt-4o", usage=None)
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        resp = await adapter.chat([LLMMessage(role="user", content="Hi")])
        assert resp.content == ""
        assert resp.usage == {}

    @patch("openai.AsyncOpenAI")
    async def test_chat_propagates_sdk_error(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("rate limited"),
        )

        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        with pytest.raises(RuntimeError, match="rate limited"):
            await adapter.chat([LLMMessage(role="user", content="Hi")])

    @patch("openai.AsyncOpenAI")
    async def test_chat_stream_yields_deltas(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        chunks = [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hel"))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
            SimpleNamespace(choices=[]),
        ]

        async def _fake_stream():
            for c in chunks:
                yield c

        mock_client.chat.completions.create = AsyncMock(return_value=_fake_stream())

        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        collected: list[str] = []
        async for delta in adapter.chat_stream([LLMMessage(role="user", content="Hi")]):
            collected.append(delta)
        assert collected == ["Hel", "lo"]

    @patch("openai.AsyncOpenAI")
    async def test_close_delegates(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        adapter = OpenAIAdapter(api_key="sk-test", model="gpt-4o")
        await adapter.close()
        mock_client.close.assert_awaited_once()


class TestAnthropicAdapter:
    def test_requires_api_key(self) -> None:
        with pytest.raises(ValueError, match="api_key is required"):
            AnthropicAdapter(api_key="")

    @patch("anthropic.AsyncAnthropic")
    async def test_chat_splits_system_message(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        usage = SimpleNamespace(input_tokens=15, output_tokens=25)
        text_block = SimpleNamespace(type="text", text="Hi there!")
        mock_response = SimpleNamespace(
            content=[text_block], model="claude-sonnet-4-20250514", usage=usage,
        )
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        adapter = AnthropicAdapter(api_key="sk-test")
        messages = [
            LLMMessage(role="system", content="Be concise."),
            LLMMessage(role="user", content="Hello"),
        ]
        resp = await adapter.chat(messages, temperature=0.3)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == [
            {"type": "text", "text": "Be concise.", "cache_control": {"type": "ephemeral"}}
        ]
        assert call_kwargs["messages"] == [{"role": "user", "content": "Hello"}]
        assert resp.content == "Hi there!"
        assert resp.usage == {"prompt_tokens": 15, "completion_tokens": 25}

    @patch("anthropic.AsyncAnthropic")
    async def test_chat_no_system_message(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        text_block = SimpleNamespace(type="text", text="Hey!")
        mock_response = SimpleNamespace(
            content=[text_block], model="claude-sonnet-4-20250514", usage=None,
        )
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        adapter = AnthropicAdapter(api_key="sk-test")
        resp = await adapter.chat([LLMMessage(role="user", content="Hey")])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert "system" not in call_kwargs
        assert resp.usage == {}

    @patch("anthropic.AsyncAnthropic")
    async def test_chat_stream(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client

        async def _fake_text_stream():
            for chunk in ["He", "llo"]:
                yield chunk

        stream_cm = AsyncMock()
        stream_cm.__aenter__ = AsyncMock(
            return_value=SimpleNamespace(text_stream=_fake_text_stream()),
        )
        stream_cm.__aexit__ = AsyncMock(return_value=False)
        mock_client.messages.stream = MagicMock(return_value=stream_cm)

        adapter = AnthropicAdapter(api_key="sk-test")
        collected: list[str] = []
        async for text in adapter.chat_stream([LLMMessage(role="user", content="Hi")]):
            collected.append(text)
        assert collected == ["He", "llo"]

    @patch("anthropic.AsyncAnthropic")
    async def test_close_delegates(self, mock_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        adapter = AnthropicAdapter(api_key="sk-test")
        await adapter.close()
        mock_client.close.assert_awaited_once()


class TestCreateLLMAdapter:
    @patch("openai.AsyncOpenAI")
    def test_openai_provider(self, mock_cls: MagicMock) -> None:
        mock_s = MagicMock()
        mock_s.llm_provider = "openai"
        mock_s.openai_api_key = "sk-openai"
        mock_s.openai_model = "gpt-4o"
        mock_s.openai_base_url = "https://api.openai.com/v1"

        with patch("arc.config.settings", mock_s):
            adapter = create_llm_adapter()
            assert isinstance(adapter, OpenAIAdapter)

    @patch("anthropic.AsyncAnthropic")
    def test_anthropic_provider(self, mock_cls: MagicMock) -> None:
        mock_s = MagicMock()
        mock_s.llm_provider = "anthropic"
        mock_s.anthropic_api_key = "sk-ant"
        mock_s.anthropic_model = "claude-sonnet-4-20250514"

        with patch("arc.config.settings", mock_s):
            adapter = create_llm_adapter()
            assert isinstance(adapter, AnthropicAdapter)

    @patch("openai.AsyncOpenAI")
    def test_deepseek_provider(self, mock_cls: MagicMock) -> None:
        mock_s = MagicMock()
        mock_s.llm_provider = "deepseek"
        mock_s.deepseek_api_key = "sk-ds"
        mock_s.deepseek_model = "deepseek-chat"
        mock_s.deepseek_base_url = "https://api.deepseek.com/v1"

        with patch("arc.config.settings", mock_s):
            adapter = create_llm_adapter()
            assert isinstance(adapter, OpenAIAdapter)

    def test_unknown_provider_raises(self) -> None:
        mock_s = MagicMock()
        mock_s.llm_provider = "gemini"

        with patch("arc.config.settings", mock_s):
            with pytest.raises(AppError, match="Unsupported LLM provider"):
                create_llm_adapter()

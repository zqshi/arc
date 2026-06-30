"""LLM adapter list_models / verify 单元测试 (v6.20 L3)。

mock client 替换 _client (不依赖真实 SDK/网络), 验证 list_models/verify 行为。
OpenAI: list_models 走 client.models.list() (返 id 列表), verify 同;
Anthropic: list_models 返静态建议 (不调 client), verify 走 1-token messages.create。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.ai.anthropic_adapter import AnthropicAdapter
from arc.application.ai.openai_adapter import OpenAIAdapter


def _mock_model(mid: str) -> MagicMock:
    m = MagicMock()
    m.id = mid
    return m


class TestOpenAIAdapterListModels:
    async def test_list_models_returns_ids(self) -> None:
        adapter = OpenAIAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(
            return_value=MagicMock(
                data=[_mock_model("gpt-4o"), _mock_model("gpt-4o-mini")]
            )
        )
        adapter._client = mock_client

        models = await adapter.list_models()
        assert models == ["gpt-4o", "gpt-4o-mini"]

    async def test_list_models_propagates_error(self) -> None:
        adapter = OpenAIAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(side_effect=RuntimeError("401 unauthorized"))
        adapter._client = mock_client

        with pytest.raises(RuntimeError, match="401"):
            await adapter.list_models()


class TestOpenAIAdapterVerify:
    async def test_verify_calls_models_list(self) -> None:
        adapter = OpenAIAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=MagicMock(data=[]))
        adapter._client = mock_client

        await adapter.verify()
        mock_client.models.list.assert_awaited()

    async def test_verify_propagates_error(self) -> None:
        adapter = OpenAIAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(side_effect=RuntimeError("401"))
        adapter._client = mock_client

        with pytest.raises(RuntimeError):
            await adapter.verify()


class TestAnthropicAdapterListModels:
    async def test_list_models_returns_static(self) -> None:
        adapter = AnthropicAdapter(api_key="sk-test")
        models = await adapter.list_models()
        assert "claude-sonnet-4-6" in models
        assert isinstance(models, list)
        assert len(models) >= 2

    async def test_list_models_does_not_call_client(self) -> None:
        adapter = AnthropicAdapter(api_key="sk-test")
        mock_client = MagicMock()
        adapter._client = mock_client

        await adapter.list_models()
        mock_client.assert_not_called()


class TestAnthropicAdapterVerify:
    async def test_verify_calls_messages_create_with_one_token(self) -> None:
        adapter = AnthropicAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=MagicMock())
        adapter._client = mock_client

        await adapter.verify()
        mock_client.messages.create.assert_awaited()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1  # 1-token 探活

    async def test_verify_propagates_error(self) -> None:
        adapter = AnthropicAdapter(api_key="sk-test")
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("401"))
        adapter._client = mock_client

        with pytest.raises(RuntimeError):
            await adapter.verify()

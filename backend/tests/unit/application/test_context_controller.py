"""Unit tests for ContextController and token estimation utilities."""

from __future__ import annotations

import pytest

from arc.application.context.controller import (
    ContextBudget,
    ContextController,
    _split_messages,
    _truncate_to_tokens,
    estimate_tokens,
)

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_pure_english(self) -> None:
        # ~0.25 tokens/char for English
        text = "Hello world this is a test"
        tokens = estimate_tokens(text)
        assert 5 <= tokens <= 10  # 26 chars / 4 ≈ 6.5

    def test_pure_chinese(self) -> None:
        # ~1.5 tokens/char for CJK
        text = "你好世界测试"
        tokens = estimate_tokens(text)
        assert 8 <= tokens <= 10  # 6 chars * 1.5 = 9

    def test_mixed_content(self) -> None:
        text = "Hello 你好 world 世界"
        tokens = estimate_tokens(text)
        assert tokens > 0

    def test_long_text_reasonable(self) -> None:
        text = "a" * 4000  # 4000 English chars ≈ 1000 tokens
        tokens = estimate_tokens(text)
        assert 900 <= tokens <= 1100


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------


class TestTruncateToTokens:
    def test_no_truncation_needed(self) -> None:
        text = "short text"
        result = _truncate_to_tokens(text, 1000)
        assert result == text

    def test_truncation_applied(self) -> None:
        text = "a" * 10000  # ~2500 tokens
        result = _truncate_to_tokens(text, 500)
        assert len(result) < len(text)
        assert "[...内容已截断...]" in result


# ---------------------------------------------------------------------------
# Message splitting
# ---------------------------------------------------------------------------


class _FakeMsg:
    def __init__(self, content: str, role_value: str = "user"):
        self.content = content
        self.role = type("R", (), {"value": role_value})()


class TestSplitMessages:
    def test_empty_messages(self) -> None:
        recent, older = _split_messages([], 10000)
        assert recent == []
        assert older == []

    def test_all_fit_in_recent(self) -> None:
        msgs = [_FakeMsg("hi"), _FakeMsg("hello")]
        recent, older = _split_messages(msgs, 10000)
        assert len(recent) == 2
        assert len(older) == 0

    def test_split_by_budget(self) -> None:
        # Each message ~ 250 tokens (1000 English chars)
        msgs = [_FakeMsg("x" * 1000) for _ in range(10)]
        recent, older = _split_messages(msgs, 600)
        # Budget ~600 tokens → fits ~2 messages of 250 each
        assert len(recent) <= 3
        assert len(older) >= 7
        assert len(recent) + len(older) == 10


# ---------------------------------------------------------------------------
# ContextBudget
# ---------------------------------------------------------------------------


class TestContextBudget:
    def test_default_available(self) -> None:
        budget = ContextBudget()
        assert budget.available == 160_000  # 200K - 40K reserve

    def test_custom_budget(self) -> None:
        budget = ContextBudget(max_context=128_000, response_reserve=30_000)
        assert budget.available == 98_000


# ---------------------------------------------------------------------------
# ContextController.assemble
# ---------------------------------------------------------------------------


class TestContextControllerAssemble:
    @pytest.mark.asyncio
    async def test_basic_assembly_no_compression(self) -> None:
        controller = ContextController(compression=None)
        msgs = [_FakeMsg("Hello", "user"), _FakeMsg("Hi there", "assistant")]

        result = await controller.assemble(
            system_prompt="You are helpful.",
            messages=msgs,
        )

        assert len(result) == 3  # system + 2 messages
        assert result[0].role == "system"
        assert "You are helpful." in result[0].content

    @pytest.mark.asyncio
    async def test_memory_context_injected(self) -> None:
        controller = ContextController(compression=None)
        msgs = [_FakeMsg("Hi", "user")]

        result = await controller.assemble(
            system_prompt="System.",
            messages=msgs,
            memory_context="Remember: user prefers Python.",
        )

        assert "Remember: user prefers Python." in result[0].content

    @pytest.mark.asyncio
    async def test_no_messages_still_works(self) -> None:
        controller = ContextController(compression=None)

        result = await controller.assemble(
            system_prompt="System prompt.",
            messages=[],
        )

        assert len(result) == 1
        assert result[0].role == "system"

    @pytest.mark.asyncio
    async def test_oversized_history_gets_trimmed(self) -> None:
        """When history exceeds budget, oldest messages are dropped."""
        budget = ContextBudget(max_context=1000, response_reserve=200)
        controller = ContextController(compression=None, budget=budget)

        # Create many large messages that exceed the budget
        msgs = [_FakeMsg("x" * 2000, "user") for _ in range(20)]

        result = await controller.assemble(
            system_prompt="S",
            messages=msgs,
        )

        # Should have system + some subset of messages (not all 20)
        assert len(result) < 21
        assert result[0].role == "system"

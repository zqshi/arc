"""Unit tests for CompressionManager (L1/L2/L3)."""

from __future__ import annotations

import pytest

from arc.application.context.compression import (
    L1_HEAD_CHARS,
    L1_TAIL_CHARS,
    L1_TRIGGER_CHARS,
    CompressionManager,
)


class _FakeMsg:
    def __init__(self, content: str, role_value: str = "user"):
        self.content = content
        self.role = type("R", (), {"value": role_value})()


# ---------------------------------------------------------------------------
# L1: 微压缩
# ---------------------------------------------------------------------------


class TestL1Compression:
    @pytest.mark.asyncio
    async def test_short_result_unchanged(self) -> None:
        cm = CompressionManager()
        result = await cm.compress_tool_result("short output")
        assert result == "short output"

    @pytest.mark.asyncio
    async def test_exactly_at_threshold_unchanged(self) -> None:
        cm = CompressionManager()
        text = "x" * L1_TRIGGER_CHARS
        result = await cm.compress_tool_result(text)
        assert result == text

    @pytest.mark.asyncio
    async def test_over_threshold_compressed(self) -> None:
        cm = CompressionManager()
        text = "x" * 20000
        result = await cm.compress_tool_result(text)

        assert len(result) < len(text)
        assert "字符已省略" in result
        # Head and tail preserved
        assert result.startswith("x" * 100)
        assert result.endswith("x" * 100)

    @pytest.mark.asyncio
    async def test_compression_preserves_head_tail(self) -> None:
        cm = CompressionManager()
        head = "HEAD_" * 600  # 3000 chars
        middle = "M" * 15000
        tail = "_TAIL" * 400  # 2000 chars
        text = head + middle + tail
        result = await cm.compress_tool_result(text)

        assert result.startswith("HEAD_")
        assert result.endswith("_TAIL")


# ---------------------------------------------------------------------------
# L2: 段落压缩 (fallback path - no LLM adapter)
# ---------------------------------------------------------------------------


class TestL2CompressionFallback:
    @pytest.mark.asyncio
    async def test_empty_messages(self) -> None:
        cm = CompressionManager(adapter=None)
        result = await cm.compress_segments([], budget=5000)
        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_truncates(self) -> None:
        cm = CompressionManager(adapter=None)
        msgs = [_FakeMsg(f"Message {i}: " + "x" * 500) for i in range(20)]
        result = await cm.compress_segments(msgs, budget=2000)

        # Should return some LLMMessage objects (fewer than input)
        assert len(result) < 20
        assert len(result) > 0


# ---------------------------------------------------------------------------
# L3: 全量压缩 (fallback path - no LLM adapter)
# ---------------------------------------------------------------------------


class TestL3CompressionFallback:
    @pytest.mark.asyncio
    async def test_empty_messages(self) -> None:
        cm = CompressionManager(adapter=None)
        result = await cm.compress_full([], budget=2000)
        assert result == []

    @pytest.mark.asyncio
    async def test_fallback_truncates(self) -> None:
        cm = CompressionManager(adapter=None)
        msgs = [_FakeMsg(f"Msg {i}: " + "y" * 1000) for i in range(30)]
        result = await cm.compress_full(msgs, budget=1000)

        assert len(result) < 30
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Format messages helper
# ---------------------------------------------------------------------------


class TestFormatMessages:
    def test_formats_roles(self) -> None:
        msgs = [_FakeMsg("你好", "user"), _FakeMsg("你好！", "assistant")]
        text = CompressionManager._format_messages(msgs)
        assert "用户" in text
        assert "AI" in text

    def test_truncates_long_messages(self) -> None:
        msgs = [_FakeMsg("x" * 5000, "user")]
        text = CompressionManager._format_messages(msgs)
        assert "[截断]" in text
        assert len(text) < 5000

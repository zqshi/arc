"""Unit tests for tool_loop #10 (LLM 错误诊断)。

LLM 诊断错误类型决定重试策略: 永久错误快速失败, 瞬时错误重试, 降级死板重试。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.execution.tool_loop import ToolAwareLoop, ToolErrorDiagnosis
from arc.application.execution.tool_loop_metrics import TOOL_MAX_RETRIES
from arc.application.execution.tools import ToolCall


def _make_loop(llm_review_fn=None):
    adapter = MagicMock()
    registry = MagicMock()
    return ToolAwareLoop(adapter, registry, llm_review_fn=llm_review_fn)


def _tc():
    return ToolCall(id="t1", name="read_file", input={"path": "/x"})


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """mock asyncio.sleep 避免重试延迟拖慢测试。"""
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())


class TestToolErrorDiagnosis:
    """ToolErrorDiagnosis.from_llm 解析 + 降级信号。"""

    def test_valid(self):
        d = ToolErrorDiagnosis.from_llm(
            {"should_retry": False, "error_type": "permission", "reason": "no access"}
        )
        assert d is not None
        assert d.should_retry is False
        assert d.error_type == "permission"
        assert d.reason == "no access"

    def test_missing_should_retry_returns_none(self):
        assert ToolErrorDiagnosis.from_llm({"error_type": "x"}) is None

    def test_non_dict_returns_none(self):
        assert ToolErrorDiagnosis.from_llm("x") is None
        assert ToolErrorDiagnosis.from_llm(None) is None

    def test_defaults(self):
        d = ToolErrorDiagnosis.from_llm({"should_retry": True})
        assert d is not None
        assert d.should_retry is True
        assert d.error_type == "unknown"
        assert d.reason == ""


class TestExecuteToolWithRetryLLM:
    """_execute_tool_with_retry LLM 诊断路径。"""

    async def test_permanent_error_fast_fail(self):
        """永久错误 LLM 诊断 should_retry=False → 快速失败, 不重试。"""
        async def llm_fn(prompt):
            return {"should_retry": False, "error_type": "permission"}

        loop = _make_loop(llm_review_fn=llm_fn)
        loop._registry.execute = AsyncMock(side_effect=PermissionError("denied"))
        result = await loop._execute_tool_with_retry(_tc())
        assert result.is_error
        assert "permission" in result.content
        assert "不重试" in result.content
        assert loop._registry.execute.await_count == 1  # 不重试

    async def test_transient_error_retries(self):
        """瞬时错误 LLM 诊断 should_retry=True → 重试到耗尽。"""
        async def llm_fn(prompt):
            return {"should_retry": True, "error_type": "network"}

        loop = _make_loop(llm_review_fn=llm_fn)
        loop._registry.execute = AsyncMock(side_effect=ConnectionError("reset"))
        result = await loop._execute_tool_with_retry(_tc())
        assert result.is_error
        assert loop._registry.execute.await_count == TOOL_MAX_RETRIES + 1

    async def test_timeout_retries_without_llm(self):
        """超时 = 瞬时, 直接重试, 不调 LLM。"""
        called: list[str] = []

        async def llm_fn(prompt):
            called.append(prompt)
            return {"should_retry": False, "error_type": "x"}

        loop = _make_loop(llm_review_fn=llm_fn)
        loop._registry.execute = AsyncMock(side_effect=asyncio.TimeoutError())
        result = await loop._execute_tool_with_retry(_tc())
        assert result.is_error
        assert called == []  # 超时不调 LLM
        assert loop._registry.execute.await_count == TOOL_MAX_RETRIES + 1

    async def test_llm_exception_degrades(self):
        """LLM 诊断异常 → 降级死板重试。"""
        async def llm_fn(prompt):
            raise RuntimeError("llm down")

        loop = _make_loop(llm_review_fn=llm_fn)
        loop._registry.execute = AsyncMock(side_effect=ValueError("bad"))
        result = await loop._execute_tool_with_retry(_tc())
        assert result.is_error
        assert loop._registry.execute.await_count == TOOL_MAX_RETRIES + 1

    async def test_no_llm_fn_degrades(self):
        """未注入 llm_review_fn → 降级死板重试。"""
        loop = _make_loop()
        loop._registry.execute = AsyncMock(side_effect=ValueError("bad"))
        result = await loop._execute_tool_with_retry(_tc())
        assert result.is_error
        assert loop._registry.execute.await_count == TOOL_MAX_RETRIES + 1

    async def test_prompt_carries_tool_and_error(self):
        """LLM prompt 应包含工具名和错误信息。"""
        captured: list[str] = []

        async def llm_fn(prompt):
            captured.append(prompt)
            return {"should_retry": False, "error_type": "permission"}

        loop = _make_loop(llm_review_fn=llm_fn)
        loop._registry.execute = AsyncMock(side_effect=PermissionError("denied"))
        await loop._execute_tool_with_retry(_tc())
        assert len(captured) == 1
        assert "read_file" in captured[0]
        assert "denied" in captured[0]

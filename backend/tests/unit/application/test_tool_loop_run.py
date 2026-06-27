"""Unit tests for ToolAwareLoop.run() — 四分支调度 (并行/串行/drift/error-loop)。

v6.10 TD-1: 为 225 行 run() 补细粒度回归测试, 支撑 async generator 转发拆分。
打桩 _call_with_tools / _parse_response 隔离 LLM 解析, 聚焦调度逻辑。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from arc.application.execution.drift_detector import DriftLevel
from arc.application.execution.tool_loop import ToolAwareLoop
from arc.application.execution.tool_loop_metrics import MAX_TOOL_TOKENS
from arc.application.execution.tools import ToolCall, ToolResult


def _make_loop(**kwargs):
    adapter = MagicMock()
    adapter.provider_type = "anthropic"
    registry = MagicMock()
    registry.execute = AsyncMock()
    registry.to_anthropic_format = MagicMock(return_value=[])
    return ToolAwareLoop(adapter, registry, **kwargs)


def _tc(name: str, *, tid: str | None = None) -> ToolCall:
    return ToolCall(id=tid or f"{name}-1", name=name, input={"path": "/x"})


def _stub(loop, parse_results):
    """桩 _call_with_tools 返回占位 response; _parse_response 依次返回 parse_results。"""
    n = len(parse_results)
    loop._call_with_tools = AsyncMock(side_effect=[{"type": "anthropic"}] * n)
    loop._parse_response = MagicMock(side_effect=list(parse_results))


async def _collect(agen):
    return [ev async for ev in agen]


class TestToolLoopRun:
    """ToolAwareLoop.run() 调度分支回归测试。"""

    async def test_text_only_response_yields_text_then_complete(self):
        loop = _make_loop()
        _stub(loop, [("hello", [])])
        events = await _collect(loop.run([]))
        assert [e.type for e in events] == ["text_delta", "complete"]
        assert events[0].content == "hello"
        loop._registry.execute.assert_not_called()

    async def test_parallel_readonly_tools_emit_calls_before_results(self):
        """并行批特征: 所有 tool_call 先 emit, 再所有 tool_result。"""
        loop = _make_loop()
        loop._registry.execute = AsyncMock(
            side_effect=[ToolResult("t1", "r1", False), ToolResult("t2", "r2", False)]
        )
        _stub(loop, [("", [_tc("read_file", tid="t1"), _tc("read_file", tid="t2")]), ("", [])])
        events = await _collect(loop.run([]))
        assert [e.type for e in events] == [
            "tool_call", "tool_call", "tool_result", "tool_result", "complete",
        ]
        assert all(e.metadata.get("parallel") for e in events[:4])
        assert loop._registry.execute.await_count == 2

    async def test_serial_mutation_tools_interleave_call_and_result(self):
        """串行批特征: call,result 交替, 无 parallel 标记。"""
        loop = _make_loop()
        loop._registry.execute = AsyncMock(
            side_effect=[ToolResult("w1", "ok1", False), ToolResult("w2", "ok2", False)]
        )
        _stub(loop, [("", [_tc("write_file", tid="w1"), _tc("write_file", tid="w2")]), ("", [])])
        events = await _collect(loop.run([]))
        assert [e.type for e in events] == [
            "tool_call", "tool_result", "tool_call", "tool_result", "complete",
        ]
        assert not events[0].metadata.get("parallel")

    async def test_mixed_tools_run_parallel_batch_then_serial(self):
        """混合: 并行批(read-only)整体先于串行批(mutation)。"""
        loop = _make_loop()
        loop._registry.execute = AsyncMock(
            side_effect=[ToolResult("r1", "rd", False), ToolResult("w1", "wd", False)]
        )
        _stub(loop, [("", [_tc("read_file", tid="r1"), _tc("write_file", tid="w1")]), ("", [])])
        events = await _collect(loop.run([]))
        assert [e.type for e in events] == [
            "tool_call", "tool_result", "tool_call", "tool_result", "complete",
        ]
        assert events[0].metadata.get("parallel") is True  # read 并行批 call
        assert events[1].metadata.get("parallel") is True  # read 并行批 result
        assert not events[2].metadata.get("parallel")  # write 串行批 call

    async def test_token_budget_exhausted_stops_without_llm_call(self):
        loop = _make_loop()
        loop._total_tokens = MAX_TOOL_TOKENS
        loop._call_with_tools = AsyncMock()
        events = await _collect(loop.run([]))
        assert events[0].type == "error"
        assert "Token" in events[0].content
        assert events[-1].type == "complete"
        loop._call_with_tools.assert_not_called()

    async def test_drift_injects_refocus_prompt_into_history(self):
        drift = MagicMock()
        drift.check_drift = AsyncMock(return_value=DriftLevel.MODERATE)
        drift.get_refocus_prompt = MagicMock(return_value="请重新聚焦")
        loop = _make_loop(drift_detector=drift)
        loop._registry.execute = AsyncMock(return_value=ToolResult("t1", "r", False))
        captured: list[list[dict]] = []

        async def call_with_tools(base, history):
            captured.append(history)
            return {"type": "anthropic"}

        loop._call_with_tools = call_with_tools
        loop._parse_response = MagicMock(side_effect=[("", [_tc("read_file")]), ("", [])])
        await _collect(loop.run([]))
        drift.check_drift.assert_awaited_once()
        drift.get_refocus_prompt.assert_called_once()
        # 第二轮调用时, tool_history 末尾应含 refocus text block
        last_block = captured[1][-1]["content"][-1]
        assert last_block["type"] == "text" and "重新聚焦" in last_block["text"]

    async def test_error_loop_terminates_when_count_ge_2(self):
        eld = MagicMock()
        eld.record_and_check = AsyncMock(return_value=True)
        eld.loop_count = 2
        eld.get_break_prompt = MagicMock(return_value="break")
        loop = _make_loop(error_loop_detector=eld)
        loop._registry.execute = AsyncMock(return_value=ToolResult("t1", "r", False))
        loop._call_with_tools = AsyncMock(side_effect=[{"type": "anthropic"}])
        loop._parse_response = MagicMock(side_effect=[("", [_tc("read_file")])])
        events = await _collect(loop.run([]))
        assert any(e.type == "error" and "死循环" in e.content for e in events)
        loop._call_with_tools.assert_awaited_once()  # break 后不再调 LLM

    async def test_error_loop_injects_break_prompt_when_count_lt_2(self):
        eld = MagicMock()
        eld.record_and_check = AsyncMock(return_value=True)
        eld.loop_count = 1
        eld.get_break_prompt = MagicMock(return_value="打破循环提示")
        loop = _make_loop(error_loop_detector=eld)
        loop._registry.execute = AsyncMock(return_value=ToolResult("t1", "r", False))
        captured: list[list[dict]] = []

        async def call_with_tools(base, history):
            captured.append(history)
            return {"type": "anthropic"}

        loop._call_with_tools = call_with_tools
        loop._parse_response = MagicMock(side_effect=[("", [_tc("read_file")]), ("", [])])
        events = await _collect(loop.run([]))
        assert not any("死循环" in e.content for e in events)  # 未终止, 继续循环
        last_block = captured[1][-1]["content"][-1]
        assert "打破循环" in last_block["text"]

    async def test_exception_yields_error_then_complete(self):
        loop = _make_loop()
        loop._call_with_tools = AsyncMock(side_effect=RuntimeError("boom"))
        events = await _collect(loop.run([]))
        assert events[0].type == "error"
        assert "boom" in events[0].content
        assert events[-1].type == "complete"

    async def test_complete_event_carries_metrics(self):
        loop = _make_loop()
        _stub(loop, [("hi", [])])
        events = await _collect(loop.run([]))
        complete = events[-1]
        assert complete.type == "complete"
        md = complete.metadata
        for key in ("message_id", "tool_rounds", "total_tokens", "elapsed_ms"):
            assert key in md
        assert loop.metrics.tool_rounds == 0
        assert loop.metrics.final_state == "complete"

    async def test_compression_shrinks_large_non_error_result(self):
        comp = MagicMock()
        comp.compress_tool_result = AsyncMock(return_value="compressed")
        loop = _make_loop(compression=comp)
        loop._registry.execute = AsyncMock(return_value=ToolResult("t1", "x" * 10001, False))
        _stub(loop, [("", [_tc("read_file")]), ("", [])])
        events = await _collect(loop.run([]))
        comp.compress_tool_result.assert_awaited_once()
        result_events = [e for e in events if e.type == "tool_result"]
        assert result_events[0].metadata["full_length"] == len("compressed")

    async def test_compression_skipped_for_error_result(self):
        comp = MagicMock()
        comp.compress_tool_result = AsyncMock(return_value="compressed")
        loop = _make_loop(compression=comp)
        loop._registry.execute = AsyncMock(return_value=ToolResult("t1", "x" * 10001, True))
        _stub(loop, [("", [_tc("read_file")]), ("", [])])
        await _collect(loop.run([]))
        comp.compress_tool_result.assert_not_called()

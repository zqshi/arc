"""Tool-aware Agent Loop for conversation mode with tool-use support.

This module extends the base AgentLoop concept to support LLM tool-use:
1. Send messages + tools to LLM
2. If LLM responds with tool_use → execute tools → feed results back → repeat
3. When LLM responds with pure text → stream to user

Supports both Anthropic (native tool_use) and OpenAI (function calling) APIs.
Read-only tools (read_file, list_directory, grep_search) execute in parallel
via asyncio.gather; mutation tools (write_file, run_command) remain serial.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import TYPE_CHECKING, AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage
from arc.application.execution.tool_helpers import (
    build_output_preview as _build_output_preview,
)
from arc.application.execution.tool_loop_adapters import (
    TOOL_ERROR_DIAGNOSIS_PROMPT,
    ToolErrorDiagnosis,
)
from arc.application.execution.tool_loop_adapters import (
    call_with_tools as _call_with_tools_fn,
)
from arc.application.execution.tool_loop_adapters import (
    parse_response as _parse_response_fn,
)
from arc.application.execution.tool_loop_metrics import (
    MAX_TOOL_ROUNDS,
    MAX_TOOL_TOKENS,
    READONLY_TOOLS,
    TOOL_MAX_RETRIES,
    TOOL_TIMEOUT_SECONDS,
    ToolLoopEvent,
    ToolLoopMetrics,
)
from arc.application.execution.tools import ToolCall, ToolRegistry, ToolResult

# re-export 保持向后兼容 (execution_engine / orchestration / 测试从 tool_loop 导入)
__all__ = [
    "ToolAwareLoop",
    "ToolErrorDiagnosis",
    "ToolLoopMetrics",
    "ToolLoopEvent",
    "MAX_TOOL_ROUNDS",
    "MAX_TOOL_TOKENS",
    "TOOL_TIMEOUT_SECONDS",
    "TOOL_MAX_RETRIES",
    "READONLY_TOOLS",
]

if TYPE_CHECKING:
    from arc.application.context.compression import CompressionManager
    from arc.application.execution.drift_detector import DriftDetector
    from arc.application.execution.error_loop_detector import ErrorLoopDetector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main tool loop
# ---------------------------------------------------------------------------


class ToolAwareLoop:
    """Manages LLM generation with tool-use support.

    Unlike the base AgentLoop which only handles text continuation,
    this loop handles the full tool-use cycle:
    LLM → tool_call → execute → tool_result → LLM → ... → text response
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        registry: ToolRegistry,
        *,
        max_tokens_per_call: int = 16384,
        compression: CompressionManager | None = None,
        drift_detector: DriftDetector | None = None,
        error_loop_detector: ErrorLoopDetector | None = None,
        llm_review_fn=None,
    ):
        self._adapter = adapter
        self._registry = registry
        self._max_tokens = max_tokens_per_call
        self._compression = compression
        self._drift_detector = drift_detector
        self._error_loop_detector = error_loop_detector
        self._llm_review_fn = llm_review_fn  # None → 降级死板重试
        self._total_tokens = 0
        self._tool_rounds = 0
        self._metrics = ToolLoopMetrics()

    @property
    def metrics(self) -> ToolLoopMetrics:
        return self._metrics

    async def run(
        self,
        messages: list[LLMMessage],
    ) -> AsyncIterator[ToolLoopEvent]:
        """Execute the tool-use loop, yielding events for the frontend."""
        start = time.monotonic()
        tool_history: list[dict] = []
        message_id = str(uuid.uuid4())

        try:
            while self._tool_rounds < MAX_TOOL_ROUNDS:
                if self._total_tokens >= MAX_TOOL_TOKENS:
                    yield ToolLoopEvent(
                        type="error",
                        content="Token 预算耗尽，已停止工具调用",
                    )
                    break

                response = await self._call_with_tools(messages, tool_history)
                text_content, tool_calls = self._parse_response(response)

                if text_content:
                    yield ToolLoopEvent(
                        type="text_delta",
                        content=text_content,
                        metadata={"message_id": message_id},
                    )

                if not tool_calls:
                    break

                self._tool_rounds += 1
                self._record_assistant_turn(tool_history, text_content, tool_calls)

                readonly_calls = [tc for tc in tool_calls if tc.name in READONLY_TOOLS]
                mutation_calls = [tc for tc in tool_calls if tc.name not in READONLY_TOOLS]

                tool_results_content: list[dict] = []
                async for event in self._run_parallel_batch(
                    readonly_calls, tool_results_content
                ):
                    yield event
                async for event in self._run_serial_batch(
                    mutation_calls, tool_results_content
                ):
                    yield event

                self._record_tool_results(tool_history, tool_calls, tool_results_content)
                await self._check_drift(tool_calls, tool_history)

                error_events, should_break = await self._detect_error_loop(
                    tool_calls, tool_results_content, tool_history
                )
                for event in error_events:
                    yield event
                if should_break:
                    break

                self._log_round(tool_calls, readonly_calls, mutation_calls)

        except Exception as exc:
            logger.error("tool_loop.error: %s", exc, exc_info=True)
            yield ToolLoopEvent(type="error", content=f"工具循环异常: {exc}")

        elapsed_ms = self._finalize_metrics(start)
        yield ToolLoopEvent(
            type="complete",
            metadata={
                "message_id": message_id,
                "tool_rounds": self._tool_rounds,
                "total_tokens": self._total_tokens,
                "elapsed_ms": elapsed_ms,
            },
        )

    async def _run_parallel_batch(
        self, readonly_calls: list[ToolCall], results_out: list[dict]
    ) -> AsyncIterator[ToolLoopEvent]:
        """并行执行 read-only 工具: 先 emit 全部 tool_call, 再 gather 执行, 再 emit tool_result。

        结果 dict append 到 results_out (供 tool_history 按原序回填)。
        """
        if not readonly_calls:
            return

        for tc in readonly_calls:
            yield ToolLoopEvent(
                type="tool_call",
                content=tc.name,
                metadata={
                    "tool_id": tc.id,
                    "input": tc.input,
                    "round": self._tool_rounds,
                    "parallel": True,
                },
            )

        results = await asyncio.gather(
            *[self._execute_tool_with_retry(tc) for tc in readonly_calls],
        )

        for tc, result in zip(readonly_calls, results):
            result = await self._maybe_compress(result)
            yield ToolLoopEvent(
                type="tool_result",
                content=_build_output_preview(tc.name, tc.input, result),
                metadata={
                    "tool_id": tc.id,
                    "tool_name": tc.name,
                    "is_error": result.is_error,
                    "full_length": len(result.content),
                    "parallel": True,
                },
            )
            results_out.append(self._tool_result_entry(tc, result))

    async def _run_serial_batch(
        self, mutation_calls: list[ToolCall], results_out: list[dict]
    ) -> AsyncIterator[ToolLoopEvent]:
        """串行执行 mutation 工具: 逐个 emit tool_call → 执行 → emit tool_result。"""
        for tc in mutation_calls:
            yield ToolLoopEvent(
                type="tool_call",
                content=tc.name,
                metadata={
                    "tool_id": tc.id,
                    "input": tc.input,
                    "round": self._tool_rounds,
                },
            )

            result = await self._execute_tool_with_retry(tc)
            result = await self._maybe_compress(result)
            yield ToolLoopEvent(
                type="tool_result",
                content=_build_output_preview(tc.name, tc.input, result),
                metadata={
                    "tool_id": tc.id,
                    "tool_name": tc.name,
                    "is_error": result.is_error,
                    "full_length": len(result.content),
                },
            )
            results_out.append(self._tool_result_entry(tc, result))

    async def _maybe_compress(self, result: ToolResult) -> ToolResult:
        """L1 压缩: 缩减 >10000 字符的非错误工具结果; 错误/小结果原样返回。"""
        if (
            self._compression
            and not result.is_error
            and len(result.content) > 10000
        ):
            compressed = await self._compression.compress_tool_result(result.content)
            return ToolResult(
                tool_use_id=result.tool_use_id,
                content=compressed,
                is_error=result.is_error,
            )
        return result

    @staticmethod
    def _tool_result_entry(tc: ToolCall, result: ToolResult) -> dict:
        """构造 tool_history 用的 tool_result dict (仅 is_error 时带标记)。"""
        entry: dict = {
            "type": "tool_result",
            "tool_use_id": tc.id,
            "content": result.content,
        }
        if result.is_error:
            entry["is_error"] = True
        return entry

    @staticmethod
    def _record_assistant_turn(
        tool_history: list[dict],
        text_content: str,
        tool_calls: list[ToolCall],
    ) -> None:
        """记录本轮 assistant 消息 (text + tool_use blocks) 到 tool_history。"""
        assistant_content: list[dict] = []
        if text_content:
            assistant_content.append({"type": "text", "text": text_content})
        for tc in tool_calls:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.input,
            })
        tool_history.append({"role": "assistant", "content": assistant_content})

    @staticmethod
    def _record_tool_results(
        tool_history: list[dict],
        tool_calls: list[ToolCall],
        tool_results_content: list[dict],
    ) -> None:
        """按原始调用顺序回填 tool_result 到 tool_history (user 角色)。"""
        result_map = {r["tool_use_id"]: r for r in tool_results_content}
        ordered_results = [
            result_map[tc.id] for tc in tool_calls if tc.id in result_map
        ]
        tool_history.append({"role": "user", "content": ordered_results})

    async def _check_drift(
        self, tool_calls: list[ToolCall], tool_history: list[dict]
    ) -> None:
        """漂移检测 (Harness §2.3): MODERATE 及以上注入 refocus prompt。"""
        if not self._drift_detector:
            return
        from arc.application.execution.drift_detector import DriftLevel

        action_desc = ", ".join(tc.name for tc in tool_calls)
        drift = await self._drift_detector.check_drift(action_desc)
        if drift >= DriftLevel.MODERATE:
            refocus = self._drift_detector.get_refocus_prompt(drift)
            tool_history.append({
                "role": "user",
                "content": [{"type": "text", "text": refocus}],
            })

    async def _detect_error_loop(
        self,
        tool_calls: list[ToolCall],
        tool_results_content: list[dict],
        tool_history: list[dict],
    ) -> tuple[list[ToolLoopEvent], bool]:
        """死循环检测 (Harness §5.4): 返回 (待 emit 事件, 是否终止循环)。"""
        if not self._error_loop_detector:
            return [], False

        sig = "|".join(
            f"{tc.name}:{tc.input.get('path', tc.input.get('command', ''))}"
            for tc in tool_calls
        )
        result_map = {r["tool_use_id"]: r for r in tool_results_content}
        err_parts = [
            f"{tc.name}: {str(result_map.get(tc.id, {}).get('content', ''))[:80]}"
            for tc in tool_calls
            if result_map.get(tc.id, {}).get("is_error")
        ]
        error_summary = "; ".join(err_parts) if err_parts else None

        if not await self._error_loop_detector.record_and_check(
            sig, error_summary=error_summary
        ):
            return [], False

        break_prompt = self._error_loop_detector.get_break_prompt()
        if self._error_loop_detector.loop_count >= 2:
            return [
                ToolLoopEvent(type="error", content="检测到持续死循环，终止工具调用")
            ], True

        tool_history.append({
            "role": "user",
            "content": [{"type": "text", "text": break_prompt}],
        })
        return [], False

    def _log_round(
        self,
        tool_calls: list[ToolCall],
        readonly_calls: list[ToolCall],
        mutation_calls: list[ToolCall],
    ) -> None:
        logger.info(
            "tool_loop.round=%d tools=%s parallel=%d serial=%d tokens=%d",
            self._tool_rounds,
            [tc.name for tc in tool_calls],
            len(readonly_calls),
            len(mutation_calls),
            self._total_tokens,
        )

    def _finalize_metrics(self, start: float) -> int:
        """收尾 metrics 并返回 elapsed_ms (供 complete 事件复用)。"""
        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._metrics.tool_rounds = self._tool_rounds
        self._metrics.total_tokens = self._total_tokens
        self._metrics.elapsed_ms = elapsed_ms
        self._metrics.final_state = "complete"
        return elapsed_ms

    async def _execute_tool_with_retry(self, tc: ToolCall) -> ToolResult:
        """Execute a tool call with timeout and retry.

        v6.3 #10: 死板重试升级为 LLM 诊断错误类型决定重试策略。
        - 🟡 超时 = 瞬时, 直接重试 (零 LLM)
        - 🟢 非超时错误 → LLM 诊断 should_retry; 永久错误快速失败
        - 降级: LLM 失败/未注入 → 现状死板重试
        """
        last_exc: Exception | None = None
        for attempt in range(TOOL_MAX_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    self._registry.execute(tc), timeout=TOOL_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                last_exc = asyncio.TimeoutError(
                    f"工具 {tc.name} 执行超时 ({TOOL_TIMEOUT_SECONDS}s)"
                )
                logger.warning(
                    "tool_loop.tool_timeout tool=%s attempt=%d/%d",
                    tc.name, attempt + 1, TOOL_MAX_RETRIES + 1,
                )
                # 🟡 超时 = 瞬时, 直接重试 (零 LLM)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "tool_loop.tool_error tool=%s attempt=%d/%d: %s",
                    tc.name, attempt + 1, TOOL_MAX_RETRIES + 1, exc,
                )
                # 🟢 LLM 诊断: 非超时错误 → 判断是否值得重试
                if (
                    self._llm_review_fn is not None
                    and attempt < TOOL_MAX_RETRIES
                ):
                    diagnosis = await self._diagnose_tool_error(tc, exc)
                    if diagnosis is not None and not diagnosis.should_retry:
                        # 永久错误, 不重试, 快速失败
                        return ToolResult(
                            tool_use_id=tc.id,
                            content=(
                                f"工具 {tc.name} 执行失败 "
                                f"({diagnosis.error_type}, 不重试): {exc}"
                            ),
                            is_error=True,
                        )
                # 降级: LLM 失败/未注入/建议重试 → 现状重试

            if attempt < TOOL_MAX_RETRIES:
                await asyncio.sleep(1)

        # All retries exhausted — return error result instead of crashing the loop
        return ToolResult(
            tool_use_id=tc.id,
            content=f"工具 {tc.name} 执行失败 (已重试 {TOOL_MAX_RETRIES} 次): {last_exc}",
            is_error=True,
        )

    async def _diagnose_tool_error(
        self, tc: ToolCall, exc: Exception
    ) -> ToolErrorDiagnosis | None:
        """调 LLM 诊断工具错误类型, 决定是否重试。失败返回 None (降级)。"""
        prompt = TOOL_ERROR_DIAGNOSIS_PROMPT.format(
            tool_name=tc.name,
            tool_input=str(tc.input)[:200],
            error=str(exc)[:200],
        )
        try:
            data = await self._llm_review_fn(prompt)
        except Exception as diag_exc:
            logger.warning("tool error LLM diagnose failed: %s", diag_exc)
            return None
        return ToolErrorDiagnosis.from_llm(data)

    async def _call_with_tools(
        self,
        base_messages: list[LLMMessage],
        tool_history: list[dict],
    ) -> dict:
        """Call the LLM with tools via adapter.chat_with_tools()."""
        response, tokens = await _call_with_tools_fn(
            self._adapter, self._registry, self._max_tokens,
            base_messages, tool_history,
        )
        self._total_tokens += tokens
        return response

    def _parse_response(self, response: dict) -> tuple[str, list[ToolCall]]:
        """Parse LLM response into text content and tool calls."""
        return _parse_response_fn(response)

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
from arc.application.execution.tools import ToolCall, ToolRegistry, ToolResult
from arc.application.execution.tool_helpers import (
    build_output_preview as _build_output_preview,
    build_anthropic_messages_with_tools as _build_anthropic_messages_with_tools,
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
from arc.application.execution.tool_loop_adapters import (
    build_openai_messages as _build_openai_messages,
    extract_usage_tokens as _extract_usage_tokens,
    parse_anthropic as _parse_anthropic,
    parse_openai as _parse_openai,
)

# re-export 保持向后兼容 (execution_engine 等从 tool_loop 导入)
__all__ = [
    "ToolAwareLoop",
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
    ):
        self._adapter = adapter
        self._registry = registry
        self._max_tokens = max_tokens_per_call
        self._compression = compression
        self._drift_detector = drift_detector
        self._error_loop_detector = error_loop_detector
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

                # Call LLM with tools
                response = await self._call_with_tools(messages, tool_history)

                # Parse response
                text_content, tool_calls = self._parse_response(response)

                # Emit text if any
                if text_content:
                    yield ToolLoopEvent(
                        type="text_delta",
                        content=text_content,
                        metadata={"message_id": message_id},
                    )

                # If no tool calls, we're done
                if not tool_calls:
                    break

                # Execute tools
                self._tool_rounds += 1

                # Build assistant message with tool_use blocks
                assistant_content = []
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

                # Split into read-only (parallelizable) and mutation (serial) groups
                readonly_calls = [tc for tc in tool_calls if tc.name in READONLY_TOOLS]
                mutation_calls = [tc for tc in tool_calls if tc.name not in READONLY_TOOLS]

                tool_results_content: list[dict] = []

                # --- Parallel batch: read-only tools via asyncio.gather ---
                if readonly_calls:
                    # Emit all tool_call events upfront so frontend shows them together
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
                        # L1 compression: shrink large non-error tool results
                        if self._compression and not result.is_error and len(result.content) > 10000:
                            compressed = await self._compression.compress_tool_result(result.content)
                            result = ToolResult(
                                tool_use_id=result.tool_use_id,
                                content=compressed,
                                is_error=result.is_error,
                            )
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
                        tool_results_content.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result.content,
                            **({"is_error": True} if result.is_error else {}),
                        })

                # --- Serial: mutation tools (write_file, run_command) ---
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

                    # L1 compression: shrink large non-error tool results
                    if self._compression and not result.is_error and len(result.content) > 10000:
                        compressed = await self._compression.compress_tool_result(result.content)
                        result = ToolResult(
                            tool_use_id=result.tool_use_id,
                            content=compressed,
                            is_error=result.is_error,
                        )

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

                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tc.id,
                        "content": result.content,
                        **({"is_error": True} if result.is_error else {}),
                    })

                # Add tool results to history (preserve original call order for LLM)
                ordered_results = []
                result_map = {r["tool_use_id"]: r for r in tool_results_content}
                for tc in tool_calls:
                    if tc.id in result_map:
                        ordered_results.append(result_map[tc.id])
                tool_history.append({"role": "user", "content": ordered_results})

                # --- Drift detection (Harness §2.3) ---
                if self._drift_detector:
                    action_desc = ", ".join(tc.name for tc in tool_calls)
                    from arc.application.execution.drift_detector import DriftLevel
                    drift = await self._drift_detector.check_drift(action_desc)
                    if drift >= DriftLevel.MODERATE:
                        refocus = self._drift_detector.get_refocus_prompt(drift)
                        tool_history.append({
                            "role": "user",
                            "content": [{"type": "text", "text": refocus}],
                        })

                # --- Error loop detection (Harness §5.4) ---
                if self._error_loop_detector:
                    sig = "|".join(
                        f"{tc.name}:{tc.input.get('path', tc.input.get('command', ''))}"
                        for tc in tool_calls
                    )
                    err_parts = [
                        f"{tc.name}: {str(result_map.get(tc.id, {}).get('content', ''))[:80]}"
                        for tc in tool_calls
                        if result_map.get(tc.id, {}).get("is_error")
                    ]
                    error_summary = "; ".join(err_parts) if err_parts else None
                    if await self._error_loop_detector.record_and_check(
                        sig, error_summary=error_summary
                    ):
                        break_prompt = self._error_loop_detector.get_break_prompt()
                        if self._error_loop_detector.loop_count >= 2:
                            yield ToolLoopEvent(
                                type="error",
                                content="检测到持续死循环，终止工具调用",
                            )
                            break
                        tool_history.append({
                            "role": "user",
                            "content": [{"type": "text", "text": break_prompt}],
                        })

                logger.info(
                    "tool_loop.round=%d tools=%s parallel=%d serial=%d tokens=%d",
                    self._tool_rounds,
                    [tc.name for tc in tool_calls],
                    len(readonly_calls),
                    len(mutation_calls),
                    self._total_tokens,
                )

        except Exception as exc:
            logger.error("tool_loop.error: %s", exc, exc_info=True)
            yield ToolLoopEvent(type="error", content=f"工具循环异常: {exc}")

        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._metrics.tool_rounds = self._tool_rounds
        self._metrics.total_tokens = self._total_tokens
        self._metrics.elapsed_ms = elapsed_ms
        self._metrics.final_state = "complete"
        yield ToolLoopEvent(
            type="complete",
            metadata={
                "message_id": message_id,
                "tool_rounds": self._tool_rounds,
                "total_tokens": self._total_tokens,
                "elapsed_ms": elapsed_ms,
            },
        )

    async def _execute_tool_with_retry(self, tc: ToolCall) -> ToolResult:
        """Execute a tool call with timeout and retry for transient failures."""
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
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "tool_loop.tool_error tool=%s attempt=%d/%d: %s",
                    tc.name, attempt + 1, TOOL_MAX_RETRIES + 1, exc,
                )

            if attempt < TOOL_MAX_RETRIES:
                await asyncio.sleep(1)

        # All retries exhausted — return error result instead of crashing the loop
        return ToolResult(
            tool_use_id=tc.id,
            content=f"工具 {tc.name} 执行失败 (已重试 {TOOL_MAX_RETRIES} 次): {last_exc}",
            is_error=True,
        )

    async def _call_with_tools(
        self,
        base_messages: list[LLMMessage],
        tool_history: list[dict],
    ) -> dict:
        """Call the LLM with tools via adapter.chat_with_tools()."""
        provider = self._adapter.provider_type

        if provider == "anthropic":
            return await self._call_anthropic(base_messages, tool_history)
        else:
            return await self._call_openai(base_messages, tool_history)

    async def _call_anthropic(
        self,
        base_messages: list[LLMMessage],
        tool_history: list[dict],
    ) -> dict:
        """Call Anthropic API with tools via adapter."""
        system_text, chat_msgs = _build_anthropic_messages_with_tools(
            base_messages, tool_history
        )

        result = await self._adapter.chat_with_tools(
            messages=chat_msgs,
            tools=self._registry.to_anthropic_format(),
            system=system_text,
            max_tokens=self._max_tokens,
        )

        self._total_tokens += _extract_usage_tokens(result)

        return {
            "type": "anthropic",
            "content": result["content"],
            "stop_reason": result.get("stop_reason"),
        }

    async def _call_openai(
        self,
        base_messages: list[LLMMessage],
        tool_history: list[dict],
    ) -> dict:
        """Call OpenAI API with tools (function calling)."""
        formatted = _build_openai_messages(base_messages, tool_history)

        result = await self._adapter.chat_with_tools(
            messages=formatted,
            tools=self._registry.to_openai_format(),
            max_tokens=self._max_tokens,
        )

        self._total_tokens += _extract_usage_tokens(result)

        response = result["response"]
        choice = response.choices[0]
        return {
            "type": "openai",
            "message": choice.message,
            "finish_reason": choice.finish_reason,
        }

    def _parse_response(self, response: dict) -> tuple[str, list[ToolCall]]:
        """Parse LLM response into text content and tool calls."""
        if response["type"] == "anthropic":
            return _parse_anthropic(response)
        return _parse_openai(response)

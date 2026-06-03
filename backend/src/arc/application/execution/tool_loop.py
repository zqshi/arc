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
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage
from arc.application.execution.tools import ToolCall, ToolRegistry, ToolResult
from arc.application.execution.tool_helpers import (
    build_output_preview as _build_output_preview,
    build_anthropic_messages_with_tools as _build_anthropic_messages_with_tools,
)

if TYPE_CHECKING:
    from arc.application.context.compression import CompressionManager
    from arc.application.execution.drift_detector import DriftDetector
    from arc.application.execution.error_loop_detector import ErrorLoopDetector

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 25  # Safety limit: max tool-use round-trips per response
MAX_TOOL_TOKENS = 200000  # Token budget for tool-use conversations

# Tools that only read state — safe to execute concurrently.
READONLY_TOOLS = frozenset({"read_file", "list_directory", "grep_search"})


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class ToolLoopMetrics:
    """Tracks statistics for a tool-aware generation cycle."""

    loop_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    tool_rounds: int = 0
    total_tokens: int = 0
    elapsed_ms: int = 0
    final_state: str = ""


# ---------------------------------------------------------------------------
# Events emitted to the frontend via SSE
# ---------------------------------------------------------------------------


@dataclass
class ToolLoopEvent:
    """Events emitted during tool-aware generation."""

    type: str
    # Types:
    #   "text_delta"    — streaming text chunk from the LLM
    #   "tool_call"     — LLM is invoking a tool
    #   "tool_result"   — tool execution completed
    #   "thinking"      — LLM is thinking (before tool call)
    #   "complete"      — generation finished
    #   "error"         — something went wrong
    content: str = ""
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Anthropic tool-use message types
# ---------------------------------------------------------------------------

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
                        *[self._registry.execute(tc) for tc in readonly_calls],
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

                    result = await self._registry.execute(tc)

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
                    drift = self._drift_detector.check_drift(action_desc)
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
                    if self._error_loop_detector.record_and_check(sig):
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

        usage = result.get("usage", {})
        self._total_tokens += usage.get("input", 0) + usage.get("output", 0)

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
        # Build messages for OpenAI format
        formatted = []
        for m in base_messages:
            formatted.append({"role": m.role, "content": m.content})

        # Convert tool history from Anthropic format to OpenAI format
        for msg in tool_history:
            if msg["role"] == "assistant":
                # Convert assistant tool_use to OpenAI tool_calls
                content_text = ""
                tool_calls_openai = []
                for block in msg["content"]:
                    if block["type"] == "text":
                        content_text += block["text"]
                    elif block["type"] == "tool_use":
                        tool_calls_openai.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        })
                assistant_msg: dict = {"role": "assistant"}
                if content_text:
                    assistant_msg["content"] = content_text
                if tool_calls_openai:
                    assistant_msg["tool_calls"] = tool_calls_openai
                formatted.append(assistant_msg)

            elif msg["role"] == "user":
                # Convert tool_result blocks to OpenAI tool messages
                for block in msg["content"]:
                    if block["type"] == "tool_result":
                        formatted.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block["content"],
                        })

        result = await self._adapter.chat_with_tools(
            messages=formatted,
            tools=self._registry.to_openai_format(),
            max_tokens=self._max_tokens,
        )

        usage = result.get("usage", {})
        self._total_tokens += usage.get("input", 0) + usage.get("output", 0)

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
            return self._parse_anthropic(response)
        else:
            return self._parse_openai(response)

    def _parse_anthropic(self, response: dict) -> tuple[str, list[ToolCall]]:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response["content"]:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        return "\n".join(text_parts), tool_calls

    def _parse_openai(self, response: dict) -> tuple[str, list[ToolCall]]:
        message = response["message"]
        text = message.content or ""
        tool_calls: list[ToolCall] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    input_data = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    input_data = {"raw": tc.function.arguments}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    input=input_data,
                ))

        return text, tool_calls

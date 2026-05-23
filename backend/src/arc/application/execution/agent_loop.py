"""Production-grade Agent Loop engine for conversation-driven execution.

Handles multi-turn LLM streaming with:
- Automatic continuation on truncated output (finish_reason=length)
- Deliverable validation with feedback retry
- Token budget enforcement
- Wall-clock timeout
- Structured observability
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, StreamResult

logger = logging.getLogger(__name__)


class LoopState(StrEnum):
    GENERATING = "generating"
    VALIDATING = "validating"
    CONTINUING = "continuing"
    RETRYING = "retrying"
    COMPLETE = "complete"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMED_OUT = "timed_out"


@dataclass
class LoopConfig:
    max_continuations: int = 5
    max_validation_retries: int = 2
    max_tokens_per_call: int = 32768
    token_budget: int = 120000
    wall_timeout_seconds: float = 300.0
    continuation_prompt: str = (
        "你的输出被截断了。请从上次中断处精确接续，"
        "注意保持JSON结构的完整性（括号/引号配对）。"
        "不要重复已输出的内容，直接续写。"
    )
    validation_prompt_template: str = (
        "你之前输出的交付物格式有误：\n{errors}\n\n"
        "请重新输出该交付物，确保JSON格式完整且包含所有必需字段。"
    )


@dataclass
class LoopMetrics:
    loop_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    iterations: int = 0
    continuations: int = 0
    validation_retries: int = 0
    total_tokens: int = 0
    total_chunks: int = 0
    elapsed_ms: int = 0
    final_state: str = ""
    finish_reasons: list[str] = field(default_factory=list)


@dataclass
class LoopEvent:
    """Event yielded from the agent loop to the caller."""

    type: str  # chunk | continuation | validation_retry | complete | error | budget_warning
    content: str = ""
    metadata: dict = field(default_factory=dict)


class AgentLoop:
    """Runs a multi-turn LLM generation loop with continuation and validation.

    Usage::

        loop = AgentLoop(adapter, config)
        async for event in loop.run(messages, validator):
            if event.type == "chunk":
                # stream delta to client
            elif event.type == "continuation":
                # notify client of auto-continue
            elif event.type == "complete":
                # final content in event.content
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        config: LoopConfig | None = None,
    ):
        self._adapter = adapter
        self._config = config or LoopConfig()
        self._metrics = LoopMetrics()
        self._state = LoopState.GENERATING

    @property
    def metrics(self) -> LoopMetrics:
        return self._metrics

    async def run(
        self,
        messages: list[LLMMessage],
        *,
        validator: _Validator | None = None,
    ) -> AsyncIterator[LoopEvent]:
        start = time.monotonic()
        message_id = str(uuid.uuid4())
        full_content = ""
        base_messages = list(messages)

        try:
            while True:
                self._check_budget()
                self._check_timeout(start)

                self._metrics.iterations += 1
                llm_messages = self._build_messages(
                    base_messages, full_content, self._state
                )

                stream_iter, stream_result = await self._adapter.chat_stream_with_result(
                    llm_messages,
                    max_tokens=self._config.max_tokens_per_call,
                )

                if self._state == LoopState.CONTINUING:
                    yield LoopEvent(
                        type="continuation",
                        metadata={
                            "iteration": self._metrics.continuations,
                            "message_id": message_id,
                        },
                    )
                elif self._state == LoopState.RETRYING:
                    yield LoopEvent(
                        type="validation_retry",
                        metadata={
                            "retry": self._metrics.validation_retries,
                            "message_id": message_id,
                        },
                    )

                chunk_content = ""
                async for chunk in stream_iter:
                    self._check_timeout(start)
                    chunk_content += chunk
                    self._metrics.total_chunks += 1
                    yield LoopEvent(
                        type="chunk",
                        content=chunk,
                        metadata={"message_id": message_id},
                    )

                full_content += chunk_content
                self._update_token_count(stream_result)
                self._metrics.finish_reasons.append(stream_result.finish_reason)

                if stream_result.finish_reason == "length":
                    if self._metrics.continuations >= self._config.max_continuations:
                        logger.warning(
                            "agent_loop.max_continuations_reached loop=%s continuations=%d",
                            self._metrics.loop_id,
                            self._metrics.continuations,
                        )
                        break
                    self._metrics.continuations += 1
                    self._state = LoopState.CONTINUING
                    logger.info(
                        "agent_loop.continuing loop=%s iteration=%d reason=length",
                        self._metrics.loop_id,
                        self._metrics.iterations,
                    )
                    continue

                if self._is_heuristic_truncated(full_content):
                    if self._metrics.continuations >= self._config.max_continuations:
                        break
                    self._metrics.continuations += 1
                    self._state = LoopState.CONTINUING
                    logger.info(
                        "agent_loop.continuing loop=%s iteration=%d reason=heuristic",
                        self._metrics.loop_id,
                        self._metrics.iterations,
                    )
                    continue

                if validator:
                    self._state = LoopState.VALIDATING
                    errors = validator.validate(full_content)
                    if errors:
                        if self._metrics.validation_retries >= self._config.max_validation_retries:
                            logger.warning(
                                "agent_loop.validation_exhausted loop=%s errors=%s",
                                self._metrics.loop_id,
                                errors,
                            )
                            break
                        self._metrics.validation_retries += 1
                        self._state = LoopState.RETRYING
                        self._validation_errors = errors
                        full_content = ""
                        logger.info(
                            "agent_loop.retrying loop=%s retry=%d errors=%s",
                            self._metrics.loop_id,
                            self._metrics.validation_retries,
                            errors[:200],
                        )
                        continue

                break

            self._state = LoopState.COMPLETE
            self._metrics.final_state = self._state.value

        except _BudgetExceededError:
            self._state = LoopState.BUDGET_EXCEEDED
            self._metrics.final_state = self._state.value
            yield LoopEvent(
                type="budget_warning",
                metadata={
                    "total_tokens": self._metrics.total_tokens,
                    "budget": self._config.token_budget,
                },
            )
        except asyncio.TimeoutError:
            self._state = LoopState.TIMED_OUT
            self._metrics.final_state = self._state.value
            yield LoopEvent(type="error", content="生成超时，已保存部分结果")
        except Exception as exc:
            self._state = LoopState.FAILED
            self._metrics.final_state = self._state.value
            logger.error("agent_loop.error loop=%s: %s", self._metrics.loop_id, exc, exc_info=True)
            raise
        finally:
            self._metrics.elapsed_ms = int((time.monotonic() - start) * 1000)
            self._log_summary()

        yield LoopEvent(
            type="complete",
            content=full_content,
            metadata={
                "message_id": message_id,
                "metrics": {
                    "iterations": self._metrics.iterations,
                    "continuations": self._metrics.continuations,
                    "validation_retries": self._metrics.validation_retries,
                    "total_tokens": self._metrics.total_tokens,
                    "elapsed_ms": self._metrics.elapsed_ms,
                    "final_state": self._metrics.final_state,
                },
            },
        )

    def _build_messages(
        self,
        base: list[LLMMessage],
        accumulated: str,
        state: LoopState,
    ) -> list[LLMMessage]:
        if state == LoopState.GENERATING:
            return list(base)

        msgs = list(base)
        if state == LoopState.CONTINUING and accumulated:
            msgs.append(LLMMessage(role="assistant", content=accumulated))
            msgs.append(LLMMessage(role="user", content=self._config.continuation_prompt))
        elif state == LoopState.RETRYING:
            error_text = getattr(self, "_validation_errors", "格式不正确")
            feedback = self._config.validation_prompt_template.format(errors=error_text)
            msgs.append(LLMMessage(role="user", content=feedback))
        return msgs

    def _check_budget(self):
        if self._metrics.total_tokens >= self._config.token_budget:
            raise _BudgetExceededError(
                f"Token budget exceeded: {self._metrics.total_tokens}/{self._config.token_budget}"
            )

    def _check_timeout(self, start: float):
        elapsed = time.monotonic() - start
        if elapsed >= self._config.wall_timeout_seconds:
            raise asyncio.TimeoutError(
                f"Agent loop timed out after {elapsed:.0f}s"
            )

    def _update_token_count(self, result: StreamResult):
        usage = result.usage or {}
        completion = usage.get("completion_tokens") or usage.get("completion_tokens_approx", 0)
        prompt = usage.get("prompt_tokens", 0)
        self._metrics.total_tokens += completion + prompt

    @staticmethod
    def _is_heuristic_truncated(content: str) -> bool:
        stripped = content.rstrip()
        if not stripped:
            return False
        open_braces = stripped.count("{") - stripped.count("}")
        open_brackets = stripped.count("[") - stripped.count("]")
        if open_braces > 0 or open_brackets > 0:
            return True
        if stripped.count("```") % 2 != 0:
            return True
        return False

    def _log_summary(self):
        logger.info(
            "agent_loop.summary",
            extra={
                "loop_id": self._metrics.loop_id,
                "iterations": self._metrics.iterations,
                "continuations": self._metrics.continuations,
                "validation_retries": self._metrics.validation_retries,
                "total_tokens": self._metrics.total_tokens,
                "elapsed_ms": self._metrics.elapsed_ms,
                "final_state": self._metrics.final_state,
                "finish_reasons": self._metrics.finish_reasons,
            },
        )


class _BudgetExceededError(Exception):
    pass


class _Validator:
    """Base validator interface for agent loop output."""

    def validate(self, content: str) -> str | None:
        """Return error description if invalid, None if valid."""
        return None


class DeliverableValidator(_Validator):
    """Validates that extracted deliverables have required fields."""

    def __init__(self, required_fields_map: dict[str, list[str]] | None = None):
        self._required = required_fields_map or {}

    def validate(self, content: str) -> str | None:
        import json
        import re

        pattern = re.compile(
            r"\[DELIVERABLE:([\w_]+)\]\s*```(?:json)?\s*(.*?)```",
            re.DOTALL,
        )
        matches = pattern.findall(content)
        if not matches:
            return None

        errors = []
        for artifact_type, json_str in matches:
            try:
                parsed = json.loads(json_str.strip())
            except json.JSONDecodeError as e:
                errors.append(f"{artifact_type}: JSON解析失败 — {e}")
                continue

            if not isinstance(parsed, dict):
                errors.append(f"{artifact_type}: 期望JSON对象，得到 {type(parsed).__name__}")
                continue

            required = self._required.get(artifact_type, [])
            missing = [f for f in required if f not in parsed]
            if missing:
                errors.append(f"{artifact_type}: 缺少必需字段 {', '.join(missing)}")

        return "\n".join(errors) if errors else None


DELIVERABLE_REQUIRED_FIELDS: dict[str, list[str]] = {
    "requirement_spec": ["background", "user_stories", "acceptance_criteria", "boundaries"],
    "interaction_design": ["user_flows", "page_map"],
    "ui_spec": ["design_tokens", "component_specs"],
    "prototype": ["pages"],
    "tech_architecture": ["data_model", "api_design", "tech_decisions"],
    "dev_report": ["test_design", "implementation", "validation"],
    "test_report": ["criteria_verification"],
    "experience_card": ["problem", "solution", "decisions"],
}

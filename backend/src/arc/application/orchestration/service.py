"""Multi-agent orchestration service.

Implements the Orchestrator-Worker pattern:
1. Orchestrator (main model) plans whether to decompose a task
2. Workers (cheap model) execute subtasks in parallel via ToolAwareLoop
3. Orchestrator synthesizes worker results into a final response

If the orchestrator decides decomposition is unnecessary, the service
falls through to a standard single-agent ToolAwareLoop — zero overhead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import TYPE_CHECKING, AsyncIterator

from arc.application.ai.adapter_pool import AdapterPool
from arc.application.ai.llm_adapter import LLMMessage
from arc.application.orchestration.prompts import (
    PLANNING_PROMPT,
    SYNTHESIS_PROMPT,
    WORKER_PROMPT,
)
from arc.domain.orchestration.entity import OrchestrationPlan, Subtask
from arc.domain.orchestration.value_objects import SubtaskType, WorkerRole

if TYPE_CHECKING:
    from arc.application.execution.tool_loop import ToolLoopEvent
    from arc.application.execution.tools import ToolRegistry

logger = logging.getLogger(__name__)

MAX_WORKER_OUTPUT = 2000  # Max chars per worker result for synthesis
WORKER_TIMEOUT_SECONDS = 60  # Per-worker execution timeout


class OrchestrationService:
    """Orchestrates parallel sub-agent execution for complex tasks."""

    def __init__(self, pool: AdapterPool) -> None:
        self._pool = pool

    async def execute(
        self,
        messages: list[LLMMessage],
        registry: ToolRegistry,
        *,
        conversation_id: uuid.UUID | None = None,
    ) -> AsyncIterator[ToolLoopEvent]:
        """Execute with optional multi-agent orchestration.

        If the planner decides decomposition is worthwhile, spawns parallel
        workers and synthesizes. Otherwise, falls through to single-agent.
        """
        user_message = self._extract_user_message(messages)
        plan = await self._plan(user_message, conversation_id)

        if plan is None:
            # No decomposition needed — single-agent fallback
            async for event in self._single_agent(messages, registry):
                yield event
            return

        plan_id = str(plan.id)[:8]
        logger.info(
            "orchestration.start plan=%s subtasks=%d",
            plan_id, len(plan.subtasks),
        )

        yield ToolLoopEvent(
            type="orchestration_start",
            metadata={"plan_id": plan_id, "subtask_count": len(plan.subtasks)},
        )

        # Execute workers layer by layer
        worker_results: list[tuple[Subtask, str]] = []
        for layer in plan.execution_layers():
            layer_results = await asyncio.gather(
                *[
                    asyncio.wait_for(
                        self._run_worker(st, registry, plan_id),
                        timeout=WORKER_TIMEOUT_SECONDS,
                    )
                    for st in layer
                ],
                return_exceptions=True,
            )

            for st, result in zip(layer, layer_results):
                if isinstance(result, Exception):
                    st.fail(str(result))
                    output = f"[ERROR] {result}"
                    yield ToolLoopEvent(
                        type="worker_error",
                        content=str(result)[:200],
                        metadata={"worker_id": str(st.id)[:8], "plan_id": plan_id},
                    )
                else:
                    output = result
                    yield ToolLoopEvent(
                        type="worker_complete",
                        content=output[:200],
                        metadata={
                            "worker_id": str(st.id)[:8],
                            "plan_id": plan_id,
                            "tokens_used": st.tokens_used,
                            "elapsed_ms": st.elapsed_ms,
                        },
                    )
                worker_results.append((st, output))

        # Synthesis phase
        yield ToolLoopEvent(
            type="synthesis_start",
            metadata={"plan_id": plan_id},
        )

        async for event in self._synthesize(messages, user_message, worker_results):
            yield event

        plan.mark_complete()

        # --- C4: 编排可观测性 — 输出结构化的执行摘要 ---
        plan_summary = {
            "plan_id": plan_id,
            "total_tokens": plan.total_tokens,
            "worker_count": len(plan.subtasks),
            "workers": [
                {
                    "id": str(st.id)[:8],
                    "description": st.description[:100],
                    "status": st.status.value,
                    "tokens_used": st.tokens_used,
                    "elapsed_ms": st.elapsed_ms,
                }
                for st in plan.subtasks
            ],
            "layers": len(plan.execution_layers()),
            "completed_at": plan.completed_at.isoformat() if plan.completed_at else None,
        }
        yield ToolLoopEvent(
            type="orchestration_complete",
            metadata=plan_summary,
        )

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def _plan(
        self,
        user_message: str,
        conversation_id: uuid.UUID | None,
    ) -> OrchestrationPlan | None:
        """Ask the orchestrator LLM if this task should be decomposed."""
        prompt = PLANNING_PROMPT.format(user_message=user_message)
        messages = [
            LLMMessage(role="system", content="你是任务规划引擎。"),
            LLMMessage(role="user", content=prompt),
        ]

        async with self._pool.acquire() as adapter:
            response = await adapter.chat(messages, max_tokens=2048)

        # Try to parse JSON plan from response
        plan_data = self._extract_plan_json(response.content)
        if not plan_data:
            return None

        subtasks_raw = plan_data.get("subtasks", [])
        if not subtasks_raw or len(subtasks_raw) < 2:
            return None

        plan = OrchestrationPlan(
            conversation_id=conversation_id or uuid.uuid4(),
            parent_message_id=str(uuid.uuid4())[:8],
        )

        subtask_ids: list[uuid.UUID] = []
        for raw in subtasks_raw:
            task_type = _safe_enum(SubtaskType, raw.get("task_type", "read_analysis"))
            worker_role = _safe_enum(WorkerRole, raw.get("worker_role", "explorer"))
            st = plan.add_subtask(
                description=raw.get("description", ""),
                task_type=task_type,
                worker_role=worker_role,
                context_paths=raw.get("context_paths", []),
                depends_on=[
                    subtask_ids[i] for i in raw.get("depends_on", [])
                    if i < len(subtask_ids)
                ],
            )
            subtask_ids.append(st.id)

        return plan

    @staticmethod
    def _extract_plan_json(content: str) -> dict | None:
        """Extract JSON from LLM response (may be wrapped in ```json```)."""
        # Try code fence first
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None

        # Try raw JSON
        try:
            data = json.loads(content.strip())
            if isinstance(data, dict) and "subtasks" in data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        return None

    # ------------------------------------------------------------------
    # Worker execution
    # ------------------------------------------------------------------

    async def _run_worker(
        self,
        subtask: Subtask,
        registry: ToolRegistry,
        plan_id: str,
    ) -> str:
        """Execute a single worker subtask."""
        from arc.application.execution.tool_loop import ToolAwareLoop

        subtask.start()
        start = time.monotonic()

        # Context fencing: scope the registry
        readonly = subtask.worker_role == WorkerRole.EXPLORER
        scoped = registry.scoped(
            subtask.context_paths or None,
            readonly=readonly,
        )

        # Build worker messages
        worker_messages = [
            LLMMessage(role="system", content="你是代码分析 Worker。"),
            LLMMessage(
                role="user",
                content=WORKER_PROMPT.format(description=subtask.description),
            ),
        ]

        # Run with worker adapter (cheap model)
        full_output = ""
        async with self._pool.acquire_worker() as adapter:
            loop = ToolAwareLoop(adapter, scoped, max_tokens_per_call=4096)
            async for event in loop.run(worker_messages):
                if event.type == "text_delta":
                    full_output += event.content

        elapsed_ms = int((time.monotonic() - start) * 1000)
        subtask.complete(
            result=full_output[:MAX_WORKER_OUTPUT],
            tokens=loop.metrics.total_tokens,
            elapsed_ms=elapsed_ms,
        )

        logger.info(
            "orchestration.worker_done plan=%s worker=%s tokens=%d elapsed=%dms",
            plan_id, str(subtask.id)[:8], subtask.tokens_used, elapsed_ms,
        )

        return full_output[:MAX_WORKER_OUTPUT]

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesize(
        self,
        original_messages: list[LLMMessage],
        user_message: str,
        worker_results: list[tuple[Subtask, str]],
    ) -> AsyncIterator[ToolLoopEvent]:
        """Synthesize worker results into a final response via streaming."""
        results_text = "\n\n".join(
            f"### Worker: {st.description}\n{output}"
            for st, output in worker_results
        )

        synthesis_prompt = SYNTHESIS_PROMPT.format(
            user_message=user_message,
            worker_results=results_text,
        )

        messages = [
            LLMMessage(role="system", content="你是综合分析引擎。"),
            LLMMessage(role="user", content=synthesis_prompt),
        ]

        message_id = str(uuid.uuid4())
        async with self._pool.acquire() as adapter:
            stream_iter, result = await adapter.chat_stream_with_result(
                messages, max_tokens=8192,
            )
            async for chunk in stream_iter:
                yield ToolLoopEvent(
                    type="text_delta",
                    content=chunk,
                    metadata={"message_id": message_id},
                )

    # ------------------------------------------------------------------
    # Single-agent fallback
    # ------------------------------------------------------------------

    async def _single_agent(
        self,
        messages: list[LLMMessage],
        registry: ToolRegistry,
    ) -> AsyncIterator[ToolLoopEvent]:
        """Standard single-agent execution (no orchestration overhead)."""
        from arc.application.execution.tool_loop import ToolAwareLoop

        async with self._pool.acquire() as adapter:
            loop = ToolAwareLoop(adapter, registry)
            async for event in loop.run(messages):
                yield event

    @staticmethod
    def _extract_user_message(messages: list[LLMMessage]) -> str:
        """Get the last user message from the conversation."""
        for msg in reversed(messages):
            if msg.role == "user":
                return msg.content
        return ""


def _safe_enum(enum_cls, value: str):
    """Parse an enum value, falling back to the first member."""
    try:
        return enum_cls(value)
    except ValueError:
        return list(enum_cls)[0]

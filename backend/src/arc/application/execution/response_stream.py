"""generate_response_stream 的两条执行路径：tool-aware 和 text-only。

从 ConversationExecutionService.generate_response_stream 中提取，
降低 conversation_strategy.py 的行数。
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

from arc.domain.conversation.entity import Conversation

logger = logging.getLogger(__name__)


async def run_tool_aware_stream(
    conversation: Conversation,
    llm_messages: list,
    project_path: str,
) -> AsyncIterator[tuple[str | None, str, dict]]:
    """Tool-use 路径：项目有 local_path 时调用。

    Yields (message_id, full_content_so_far, chunk_dict) tuples.
    最终 yield 的 chunk_dict 包含 ``_stream_done`` 标志。
    """
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.execution.tool_loop import ToolAwareLoop
    from arc.application.execution.tools import ToolRegistry

    registry = ToolRegistry(project_path)
    message_id: str | None = None
    full_content = ""

    async with adapter_pool.acquire() as adapter:
        loop = ToolAwareLoop(adapter, registry)
        async for event in loop.run(llm_messages):
            if event.type == "text_delta":
                if message_id is None:
                    message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                full_content += event.content
                yield message_id, full_content, {"message_id": message_id, "content": event.content}

            elif event.type == "tool_call":
                yield message_id, full_content, {
                    "message_id": message_id or str(uuid.uuid4()),
                    "event": "tool_call",
                    "tool_name": event.content,
                    "tool_input": event.metadata.get("input", {}),
                    "round": event.metadata.get("round", 0),
                }

            elif event.type == "tool_result":
                yield message_id, full_content, {
                    "message_id": message_id or str(uuid.uuid4()),
                    "event": "tool_result",
                    "tool_name": event.metadata.get("tool_name", ""),
                    "output_preview": event.content,
                    "is_error": event.metadata.get("is_error", False),
                }

            elif event.type == "error":
                logger.error("Tool loop error: %s", event.content)

            elif event.type == "complete":
                if message_id is None:
                    message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                logger.info(
                    "Tool loop complete: %d rounds, %d tokens, %dms",
                    event.metadata.get("tool_rounds", 0),
                    event.metadata.get("total_tokens", 0),
                    event.metadata.get("elapsed_ms", 0),
                )

    # Sentinel: signal stream is done
    yield message_id, full_content, {"_stream_done": True, "_loop": loop}


async def run_text_only_stream(
    conversation: Conversation,
    llm_messages: list,
    loop_config,
) -> AsyncIterator[tuple[str | None, str, dict]]:
    """Text-only 路径：无 local_path 时调用。

    Yields (message_id, full_content_so_far, chunk_dict) tuples.
    最终 yield 的 chunk_dict 包含 ``_stream_done`` 标志。
    """
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.execution.agent_loop import (
        DELIVERABLE_REQUIRED_FIELDS,
        AgentLoop,
        DeliverableValidator,
    )

    validator = DeliverableValidator(DELIVERABLE_REQUIRED_FIELDS)
    message_id: str | None = None
    full_content = ""
    loop: AgentLoop | None = None

    async with adapter_pool.acquire() as adapter:
        loop = AgentLoop(adapter, loop_config)
        async for event in loop.run(llm_messages, validator=validator):
            if event.type == "chunk":
                if message_id is None:
                    message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                full_content += event.content
                yield message_id, full_content, {"message_id": message_id, "content": event.content}

            elif event.type == "continuation":
                logger.info(
                    "Agent loop continuation #%d (transparent)",
                    event.metadata.get("iteration", 0),
                )

            elif event.type == "validation_retry":
                logger.info(
                    "Agent loop validation retry #%d",
                    event.metadata.get("retry", 0),
                )

            elif event.type == "budget_warning":
                logger.warning(
                    "Agent loop budget exceeded: %s/%s tokens",
                    event.metadata.get("total_tokens"),
                    event.metadata.get("budget"),
                )

            elif event.type == "error":
                logger.error("Agent loop error: %s", event.content)

            elif event.type == "complete":
                full_content = event.content
                metrics = event.metadata.get("metrics", {})
                if message_id is None:
                    message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                logger.info(
                    "Agent loop complete: %d iters, %d conts, %dms, by=%s",
                    metrics.get("iterations", 0),
                    metrics.get("continuations", 0),
                    metrics.get("elapsed_ms", 0),
                    event.metadata.get("terminated_by", "unknown"),
                )

    # Sentinel: signal stream is done
    yield message_id, full_content, {"_stream_done": True, "_loop": loop}

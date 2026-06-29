"""上下文窗口控制器 — Harness §2 Context Control。

职责：
- Token 预算分配与监控
- 按优先级组装上下文（P0 不可压缩 → P3 优先压缩）
- 在超出预算时触发压缩
- 缓存友好的排序（静态前缀 → 动态后缀）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from arc.application.context.token_utils import estimate_tokens

if TYPE_CHECKING:
    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.context.compression import CompressionManager
    from arc.domain.conversation.entity import Message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContextBudget:
    """Token 预算配置。

    默认基于 200K context window (Anthropic Claude)。
    较小模型可通过 ContextController(budget=ContextBudget(...)) 自定义。
    """

    max_context: int = 200_000
    system_prompt: int = 3_000       # P0: 不可压缩
    memory_recall: int = 6_000       # P1: 记忆召回
    recent_turns: int = 40_000       # P1: 最近 3 轮对话
    tool_results: int = 60_000       # P2: 工具执行结果
    older_history: int = 40_000      # P3: 早期对话历史
    response_reserve: int = 40_000   # 预留给模型响应

    @property
    def available(self) -> int:
        """可用于内容的总 token 数。"""
        return self.max_context - self.response_reserve


class ContextController:
    """上下文窗口管理器。

    按 P0 → P3 优先级组装上下文，必要时触发压缩。
    输出按缓存友好顺序排列：静态 system prompt 在前，动态对话历史在后。
    """

    def __init__(
        self,
        compression: CompressionManager | None = None,
        budget: ContextBudget | None = None,
    ):
        self._compression = compression
        self._budget = budget or ContextBudget()

    async def assemble(
        self,
        system_prompt: str,
        messages: list[Message],
        *,
        memory_context: str = "",
    ) -> list:
        """按优先级组装上下文，必要时触发压缩。

        返回 LLMMessage 列表，可直接传给 LLMAdapter。

        排列顺序（缓存友好）：
        1. system prompt（静态前缀，高缓存命中）
        2. memory context（半动态）
        3. 对话历史（动态，每轮增长）
        """
        from arc.application.ai.llm_adapter import LLMMessage

        budget = self._budget
        available = budget.available

        # P0: system prompt — 不可压缩
        sys_tokens = estimate_tokens(system_prompt)
        if sys_tokens > budget.system_prompt:
            logger.warning(
                "System prompt (%d tokens) exceeds budget (%d), truncating tail",
                sys_tokens, budget.system_prompt,
            )
            system_prompt = _truncate_to_tokens(system_prompt, budget.system_prompt)
            sys_tokens = budget.system_prompt
        used = sys_tokens

        # P1: memory context
        mem_tokens = 0
        if memory_context:
            mem_tokens = estimate_tokens(memory_context)
            if mem_tokens > budget.memory_recall:
                memory_context = _truncate_to_tokens(
                    memory_context, budget.memory_recall
                )
                mem_tokens = budget.memory_recall
            used += mem_tokens

        # 计算剩余可用给对话历史的 tokens
        history_budget = available - used

        # 分割消息：最近 N 轮 (P1) vs 早期历史 (P3)
        recent, older = _split_messages(messages, budget.recent_turns)

        recent_tokens = sum(estimate_tokens(m.content) for m in recent)
        older_tokens = sum(estimate_tokens(m.content) for m in older)
        total_history = recent_tokens + older_tokens

        # 计算使用率 → 决定是否压缩
        usage_ratio = (used + total_history) / budget.max_context

        if usage_ratio > 0.85 and self._compression and older:
            # L3 全量压缩
            logger.info(
                "Context usage %.0f%% > 85%%, triggering L3 full compression",
                usage_ratio * 100,
            )
            compressed = await self._compression.compress_full(
                older, budget=min(history_budget - recent_tokens, budget.older_history)
            )
            history_messages = compressed + [
                LLMMessage(role=m.role.value, content=m.content) for m in recent
            ]
        elif usage_ratio > 0.70 and self._compression and older:
            # L2 段落压缩
            logger.info(
                "Context usage %.0f%% > 70%%, triggering L2 segment compression",
                usage_ratio * 100,
            )
            compressed = await self._compression.compress_segments(
                older, budget=min(history_budget - recent_tokens, budget.older_history)
            )
            history_messages = compressed + [
                LLMMessage(role=m.role.value, content=m.content) for m in recent
            ]
        elif total_history > history_budget:
            # 简单截断：丢弃最早的消息直到放得下
            logger.info(
                "History (%d tokens) exceeds budget (%d), trimming oldest",
                total_history, history_budget,
            )
            history_messages = _trim_to_budget(messages, history_budget)
        else:
            # 全量保留
            history_messages = [
                LLMMessage(role=m.role.value, content=m.content) for m in messages
            ]

        # 组装最终消息列表（缓存友好顺序）
        result: list[LLMMessage] = []

        # 1. System prompt（含 memory context）
        full_system = system_prompt
        if memory_context:
            full_system = system_prompt + "\n\n" + memory_context
        result.append(LLMMessage(role="system", content=full_system))

        # 2. 对话历史
        result.extend(history_messages)

        total_tokens = sum(estimate_tokens(m.content) for m in result)
        logger.debug(
            "Context assembled: %d messages, ~%d tokens (%.0f%% of %d)",
            len(result), total_tokens,
            total_tokens / budget.max_context * 100, budget.max_context,
        )

        return result


# ------------------------------------------------------------------
# Token estimation utilities
# ------------------------------------------------------------------


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """粗略截断文本到指定 token 数。"""
    current = estimate_tokens(text)
    if current <= max_tokens:
        return text
    # 按比例截断
    ratio = max_tokens / current
    cut_point = int(len(text) * ratio * 0.95)  # 留 5% 余量
    return text[:cut_point] + "\n[...内容已截断...]"


def _split_messages(
    messages: list, recent_budget: int,
) -> tuple[list, list]:
    """将消息分为最近 N 轮和早期历史。

    从末尾向前累计 token，直到达到 recent_budget。
    """
    if not messages:
        return [], []

    recent: list = []
    running_tokens = 0

    for msg in reversed(messages):
        msg_tokens = estimate_tokens(msg.content)
        if running_tokens + msg_tokens > recent_budget and recent:
            break
        recent.insert(0, msg)
        running_tokens += msg_tokens

    older = messages[: len(messages) - len(recent)]
    return recent, older


def _trim_to_budget(messages: list, budget: int) -> list:
    """从最新消息开始保留，直到达到 token 预算。"""
    from arc.application.ai.llm_adapter import LLMMessage

    result: list[LLMMessage] = []
    running = 0

    for msg in reversed(messages):
        tokens = estimate_tokens(msg.content)
        if running + tokens > budget and result:
            break
        result.insert(0, LLMMessage(role=msg.role.value, content=msg.content))
        running += tokens

    return result

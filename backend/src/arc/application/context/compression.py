"""三级压缩管理器 — Harness §3 Compression。

L1 微压缩: 截断超长工具输出 → head + tail + 中间摘要 (规则，< 10ms)
L2 段落压缩: LLM 摘要早期对话，保留关键决策和失败记录 (1-3s)
L3 全量压缩: 重建最小上下文，仅保留目标/进度/禁止事项 (3-8s)

设计原则:
- 压缩 prompt 必须显式要求保留"失败的尝试及其原因"
- 采用提取式优先（引用原文），降低信息幻觉风险
- L1 纯规则不依赖 LLM，L2/L3 使用 LLM 但有降级方案
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.application.ai.llm_adapter import LLMAdapter
    from arc.domain.conversation.entity import Message

logger = logging.getLogger(__name__)

# L1 压缩参数
L1_HEAD_CHARS = 3000
L1_TAIL_CHARS = 2000
L1_TRIGGER_CHARS = 10000

# L2/L3 压缩 prompt 模板
L2_COMPRESSION_PROMPT = """\
请将以下对话历史压缩为结构化摘要。

## 必须保留的信息（按重要性排序）：
1. 所有用户的原始请求和意图
2. 所有已完成的操作及其结果
3. 所有失败的尝试及其失败原因（极其重要！不保留=重复犯错）
4. 当前正在进行的任务和进度
5. 关键决策及其推理过程

## 必须丢弃的信息：
1. 工具调用的详细输出（保留摘要即可）
2. 探索性的中间推理（保留结论）
3. 重复的确认对话

## 输出格式（严格遵守）：
### 已完成
- [操作]: [结果]

### 失败记录
- [尝试]: [失败原因]

### 当前状态
- 正在进行: [描述]
- 关键上下文: [描述]

### 待办事项
- [任务]

## 对话历史：
{conversation_history}
"""

L3_COMPRESSION_PROMPT = """\
将以下对话压缩为最小必要上下文（目标 < 500 词）。

只保留：
1. 最终目标是什么
2. 目前完成了什么（一句话概括每项）
3. 接下来必须做什么
4. 绝对不能做什么（已知的失败路径）

{full_conversation}
"""


class CompressionManager:
    """三级压缩管理器。"""

    def __init__(self, adapter: LLMAdapter | None = None):
        self._adapter = adapter

    # ------------------------------------------------------------------
    # L1: 微压缩（纯规则，不依赖 LLM）
    # ------------------------------------------------------------------

    async def compress_tool_result(self, result: str) -> str:
        """L1 微压缩：超长工具输出 → head + tail + 中间摘要。

        触发条件: len(result) > L1_TRIGGER_CHARS
        延迟: < 10ms
        信息损失: 极低
        """
        if len(result) <= L1_TRIGGER_CHARS:
            return result

        head = result[:L1_HEAD_CHARS]
        tail = result[-L1_TAIL_CHARS:]
        omitted = len(result) - L1_HEAD_CHARS - L1_TAIL_CHARS

        compressed = (
            f"{head}\n"
            f"\n[... 中间 {omitted} 字符已省略。"
            f"如需查看完整内容，请使用工具重新读取指定行范围 ...]\n\n"
            f"{tail}"
        )

        logger.debug(
            "L1 compression: %d → %d chars (%.0f%% reduction)",
            len(result), len(compressed),
            (1 - len(compressed) / len(result)) * 100,
        )
        return compressed

    # ------------------------------------------------------------------
    # L2: 段落压缩（LLM 摘要，保留关键决策）
    # ------------------------------------------------------------------

    async def compress_segments(
        self,
        messages: list[Message],
        budget: int = 40000,
    ) -> list:
        """L2 段落压缩：对早期对话进行 LLM 摘要。

        触发条件: context 使用率 > 70%
        延迟: 1-3s
        信息损失: 低-中（保留核心决策）
        """
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.context.controller import estimate_tokens

        if not messages:
            return []

        # 无 LLM adapter → 降级为简单截断
        if not self._adapter:
            return self._fallback_truncate(messages, budget)

        # 将消息格式化为对话文本
        conversation_text = self._format_messages(messages)

        try:
            prompt = L2_COMPRESSION_PROMPT.format(
                conversation_history=conversation_text
            )
            response = await self._adapter.chat(
                [
                    LLMMessage(role="system", content="你是一个对话压缩专家。"),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=4096,
            )
            summary = response.content.strip()

            summary_tokens = estimate_tokens(summary)
            logger.info(
                "L2 compression: %d messages → %d tokens summary",
                len(messages), summary_tokens,
            )

            return [LLMMessage(
                role="system",
                content=f"[以下是早期对话的压缩摘要]\n\n{summary}",
            )]

        except Exception as exc:
            logger.warning("L2 compression failed, falling back: %s", exc)
            return self._fallback_truncate(messages, budget)

    # ------------------------------------------------------------------
    # L3: 全量压缩（LLM 重建最小上下文）
    # ------------------------------------------------------------------

    async def compress_full(
        self,
        messages: list[Message],
        budget: int = 20000,
    ) -> list:
        """L3 全量压缩：重建最小上下文。

        触发条件: context 使用率 > 85%
        延迟: 3-8s
        信息损失: 中-高（仅保留关键事实）
        """
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.context.controller import estimate_tokens

        if not messages:
            return []

        if not self._adapter:
            return self._fallback_truncate(messages, budget)

        conversation_text = self._format_messages(messages)

        try:
            prompt = L3_COMPRESSION_PROMPT.format(
                full_conversation=conversation_text
            )
            response = await self._adapter.chat(
                [
                    LLMMessage(role="system", content="你是一个对话压缩专家。"),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            summary = response.content.strip()

            summary_tokens = estimate_tokens(summary)
            logger.info(
                "L3 compression: %d messages → %d tokens (target was %d)",
                len(messages), summary_tokens, budget,
            )

            return [LLMMessage(
                role="system",
                content=f"[以下是对话的关键摘要——完整历史已压缩]\n\n{summary}",
            )]

        except Exception as exc:
            logger.warning("L3 compression failed, falling back: %s", exc)
            return self._fallback_truncate(messages, budget)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_messages(messages: list[Message]) -> str:
        """将 Message 列表格式化为可读文本。"""
        parts = []
        for msg in messages:
            role_label = {"user": "用户", "assistant": "AI", "system": "系统"}.get(
                msg.role.value, msg.role.value
            )
            content = msg.content
            if len(content) > 2000:
                content = content[:2000] + "...[截断]"
            parts.append(f"**{role_label}**: {content}")
        return "\n\n".join(parts)

    @staticmethod
    def _fallback_truncate(messages: list, budget: int) -> list:
        """降级方案：无 LLM 时保留最近的消息。"""
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.context.controller import estimate_tokens

        result = []
        running = 0
        for msg in reversed(messages):
            tokens = estimate_tokens(msg.content)
            if running + tokens > budget and result:
                break
            result.insert(0, LLMMessage(role=msg.role.value, content=msg.content))
            running += tokens
        return result

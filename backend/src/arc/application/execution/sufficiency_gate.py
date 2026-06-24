"""sufficiency 产出门禁 — 产出 requirement_spec 前判断对话信息是否足够。

v6.0 #7 (prompt-upgrade-plan): 把躺尸的 INPUT_SUFFICIENCY_PROMPT 三维评估
(target_users/core_problem/feature_direction) 接到 requirement_spec 产出门禁。

设计原则:
- 产出前门禁: LLM 三维评估作为"确认 requirement_spec 进下一阶段"前的硬门禁,
  不是每轮注入(避免每轮多一次 LLM 调用)。每轮引导由 SufficiencyHintProvider
  轮次计数承担(轻量), 质量判断由本门禁承担(语义)。职责分离。
- 复用 > 新建: LLM 调用复用 conversation_gate 的 resilient adapter + extract_json 模式。
- 降级兜底: LLM 不可用/解析失败 → sufficient=True 放行, 不阻断主流程(遵循降级原则)。

与 conversation_gate 的区别:
- conversation_gate 评估"已生成 artifact 内容字段质量"(产出后)
- sufficiency_gate 评估"对话历史信息是否足够开始产出"(产出前)
两者正交, 互补。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SufficiencyDimension:
    """单个需求维度的充分性状态。"""

    status: str  # clear / vague / missing
    evidence: str = ""

    @classmethod
    def from_dict(cls, data: dict | None) -> "SufficiencyDimension":
        data = data or {}
        return cls(
            status=str(data.get("status", "missing")),
            evidence=str(data.get("evidence", "")),
        )


@dataclass
class SufficiencyResult:
    """对话信息充分性评估结果。"""

    sufficient: bool
    target_users: SufficiencyDimension = field(
        default_factory=lambda: SufficiencyDimension("missing")
    )
    core_problem: SufficiencyDimension = field(
        default_factory=lambda: SufficiencyDimension("missing")
    )
    feature_direction: SufficiencyDimension = field(
        default_factory=lambda: SufficiencyDimension("missing")
    )
    follow_up_questions: list[str] = field(default_factory=list)

    @classmethod
    def from_llm(cls, data: dict) -> "SufficiencyResult":
        """从 LLM 输出 JSON 构造。缺 sufficient 字段视为降级放行。"""
        if not isinstance(data, dict) or "sufficient" not in data:
            return cls(sufficient=True)  # 降级放行
        return cls(
            sufficient=bool(data.get("sufficient", True)),
            target_users=SufficiencyDimension.from_dict(data.get("target_users")),
            core_problem=SufficiencyDimension.from_dict(data.get("core_problem")),
            feature_direction=SufficiencyDimension.from_dict(
                data.get("feature_direction")
            ),
            follow_up_questions=list(data.get("follow_up_questions") or []),
        )


async def evaluate_sufficiency(
    *,
    title: str,
    description: str,
    conversation_summary: str,
    llm_review_fn=None,
) -> SufficiencyResult:
    """评估对话信息是否足够开始深度分析(产出 requirement_spec)。

    调 INPUT_SUFFICIENCY_PROMPT 三维评估。降级: LLM 失败/解析失败 → sufficient=True 放行。

    Args:
        title/description: 需求(todo)标题与描述。
        conversation_summary: 对话历史摘要(调用方拼接, 过滤 user 消息)。
        llm_review_fn: 可注入 (prompt) -> dict, 用于测试; None 用默认 resilient adapter。
    """
    from arc.application.pipeline.prompts import INPUT_SUFFICIENCY_PROMPT

    prompt = INPUT_SUFFICIENCY_PROMPT.format(
        title=title or "",
        description=description or "",
        conversation_summary=conversation_summary or "",
    )

    try:
        if llm_review_fn is not None:
            data = await llm_review_fn(prompt)
        else:
            data = await _default_llm_review(prompt)
    except Exception as exc:
        logger.warning("sufficiency gate LLM review failed, degrade to pass: %s", exc)
        return SufficiencyResult(sufficient=True)

    return SufficiencyResult.from_llm(data if isinstance(data, dict) else {})


async def _default_llm_review(prompt: str) -> dict:
    """默认 LLM 评审实现 (复用 conversation_gate 的 resilient adapter 模式)。"""
    from arc.application.ai.json_extract import extract_json
    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.ai.resilience import create_resilient_adapter

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat([LLMMessage(role="user", content=prompt)])
    finally:
        await adapter.close()
    return extract_json(response.content)

"""需求信息充分性检测 — 每轮对话后自动判断是否具备生成产出物的条件。

来源: analysis-to-prd skill Step 2 改造
职责:
  - 检测三项必要信号: target_users / core_problem / feature_direction
  - 不足时生成追问建议（而非阻断）
  - 充分时注入"可以开始产出"的信号

设计原则:
  - 轻量: 每次调用消耗 ~500 tokens，不阻塞主流程
  - 渐进: 随对话轮次积累逐步从 insufficient → sufficient
  - 非阻断: 返回 metadata，不抛异常
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

from arc.application.ai.json_extract import extract_json

logger = logging.getLogger(__name__)


class SignalStatus(StrEnum):
    CLEAR = "clear"
    VAGUE = "vague"
    MISSING = "missing"


@dataclass
class SufficiencyResult:
    """充分性检测结果"""

    sufficient: bool
    signals: dict[str, SignalStatus] = field(default_factory=dict)
    follow_up_questions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_metadata(self) -> dict:
        return {
            "sufficient": self.sufficient,
            "signals": {k: v.value for k, v in self.signals.items()},
            "follow_up_questions": self.follow_up_questions,
            "confidence": self.confidence,
        }


# 三项必要信号定义
REQUIRED_SIGNALS = {
    "target_users": "能回答'谁在用这个功能'——具体的用户角色或画像",
    "core_problem": "能回答'用户遇到了什么痛点'——明确的问题描述",
    "feature_direction": "能回答'大致要做什么'——功能方向或解法概要",
}

SUFFICIENCY_CHECK_PROMPT = """\
评估以下需求对话是否已收集到足够信息来生成结构化产出物。

## 需求信息
标题: {title}
描述: {description}

## 对话摘要（最近内容）
{conversation_summary}

## 检测三项必要信号

对每项给出状态 (clear/vague/missing) 和证据:
- **target_users**: 能否回答"谁在用这个功能"？
- **core_problem**: 能否回答"用户遇到了什么痛点"？
- **feature_direction**: 能否回答"大致要做什么"？

## 输出 JSON

```json
{{
  "sufficient": true/false,
  "target_users": {{"status": "clear/vague/missing", "evidence": "从对话中提取的证据"}},
  "core_problem": {{"status": "clear/vague/missing", "evidence": ""}},
  "feature_direction": {{"status": "clear/vague/missing", "evidence": ""}},
  "confidence": 0.0-1.0,
  "follow_up_questions": ["（仅 sufficient=false 时）最关键的 1-2 个追问"]
}}
```"""


async def check_sufficiency(
    title: str,
    description: str,
    conversation_messages: list,
    *,
    max_context_messages: int = 10,
) -> SufficiencyResult:
    """检测当前对话信息是否足够生成产出物。

    轻量级调用 — 只取最近 N 条消息做摘要，控制 token 消耗。
    """
    from arc.application.ai.resilience import create_resilient_adapter
    from arc.application.ai.llm_adapter import LLMMessage

    # 构建对话摘要
    recent = conversation_messages[-max_context_messages:]
    summary_parts = []
    for msg in recent:
        role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
        content = msg.content[:300] if msg.content else ""
        if role != "system":
            summary_parts.append(f"[{role}] {content}")
    conversation_summary = "\n".join(summary_parts) or "（暂无对话）"

    prompt = SUFFICIENCY_CHECK_PROMPT.format(
        title=title or "未命名",
        description=description or "无描述",
        conversation_summary=conversation_summary,
    )

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat([LLMMessage(role="user", content=prompt)])
    finally:
        await adapter.close()

    result_data = extract_json(response.content)
    if not isinstance(result_data, dict):
        logger.warning("Sufficiency check parse failed, defaulting to insufficient")
        return SufficiencyResult(
            sufficient=False,
            signals={k: SignalStatus.MISSING for k in REQUIRED_SIGNALS},
            follow_up_questions=["请描述你想做什么、给谁用、解决什么问题"],
            confidence=0.0,
        )

    signals = {}
    for key in REQUIRED_SIGNALS:
        signal_data = result_data.get(key, {})
        if isinstance(signal_data, dict):
            status_str = signal_data.get("status", "missing")
        else:
            status_str = "missing"
        try:
            signals[key] = SignalStatus(status_str)
        except ValueError:
            signals[key] = SignalStatus.MISSING

    sufficient = result_data.get("sufficient", False)
    # 即使 LLM 说 sufficient=True，如果有 missing 信号，强制不通过
    if any(s == SignalStatus.MISSING for s in signals.values()):
        sufficient = False

    return SufficiencyResult(
        sufficient=sufficient,
        signals=signals,
        follow_up_questions=result_data.get("follow_up_questions", []),
        confidence=result_data.get("confidence", 0.0),
    )


def build_sufficiency_nudge(result: SufficiencyResult) -> str:
    """基于充分性检测结果，生成注入到下一轮 prompt 的引导提示。

    - sufficient=True → 注入"信息充分，可以开始产出"信号
    - sufficient=False → 注入缺失项 + 追问建议
    """
    if result.sufficient:
        return (
            "[信息充分] 当前收集到的信息已足够开始产出结构化交付物。"
            "如果你认为需求已经清晰，可以开始输出对应的交付物。"
        )

    missing = [k for k, v in result.signals.items() if v == SignalStatus.MISSING]
    vague = [k for k, v in result.signals.items() if v == SignalStatus.VAGUE]

    parts = ["[信息不足] 当前还缺少关键信息，请继续引导用户补充："]

    if missing:
        labels = {"target_users": "目标用户", "core_problem": "核心问题", "feature_direction": "功能方向"}
        missing_labels = [labels.get(k, k) for k in missing]
        parts.append(f"- 缺失: {', '.join(missing_labels)}")

    if vague:
        labels = {"target_users": "目标用户", "core_problem": "核心问题", "feature_direction": "功能方向"}
        vague_labels = [labels.get(k, k) for k in vague]
        parts.append(f"- 模糊需澄清: {', '.join(vague_labels)}")

    if result.follow_up_questions:
        parts.append("- 建议追问: " + "; ".join(result.follow_up_questions[:2]))

    return "\n".join(parts)

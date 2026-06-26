"""对话模式质量门禁 — 按 ArtifactType + ProcessConstraint 分级评估。

与 pipeline/gate.py 的 evaluate_gate 的区别:
- evaluate_gate 按 PhaseType 工作 (phase 主产物的合并内容)
- 对话模式按 ArtifactType 工作 (每个 artifact 独立评估)，一个 phase 多 artifact
- 按 GateProfile 分级 (free/moderate/strict 不同 score 阈值和方法论深度)

复用关系 (元原则: 复用 > 新建):
- 结构校验: 按 artifact 用 DELIVERABLE_REQUIRED_FIELDS (粒度精确，区别于 gate 的 phase 级)
- 方法论/交叉一致性: 仅对 phase 主产物复用 gate._check_methodology/_check_cross_consistency
  (这俩按 phase 设计，假设 content 是主产物格式；非主产物跑会误判，故限制为主产物)
- LLM 评审: 复用 GATE_EVALUATION_PROMPT

质量真相单一来源: 结果经 to_quality() 写入 artifact.content["_quality"]，
DeliverableTracker.is_quality_complete(qualified_types) 读它。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from arc.application.execution.gate_threshold import get_profile
from arc.domain.artifact.value_objects import (
    DELIVERABLE_REQUIRED_FIELDS,
    PHASE_ARTIFACT_MAP,
    PHASE_PRIMARY_ARTIFACT,
    ArtifactType,
)
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.project.value_objects import ProcessConstraint

logger = logging.getLogger(__name__)

# 占位符黑名单 — 复用 gate.py check_required_fields 的判定口径
_PLACEHOLDER_VALUES = frozenset({"待补充", "未定义", "暂无", "（尚未生成）", "N/A"})


@dataclass
class ConversationGateResult:
    """对话模式门禁评估结果。"""

    passed: bool
    score: int
    gaps: list[str] = field(default_factory=list)
    suggestion: str = ""
    threshold: int = 0
    blocked_by_dependency: bool = False
    dependency_warning: list[str] = field(default_factory=list)
    checked_layers: list[str] = field(default_factory=list)

    def to_quality(self) -> dict:
        """转为 artifact.content["_quality"] 的存储格式。"""
        return {
            "passed": self.passed,
            "score": self.score,
            "gaps": self.gaps[:10],
            "suggestion": self.suggestion,
            "threshold": self.threshold,
            "blocked_by_dependency": self.blocked_by_dependency,
            "dependency_warning": self.dependency_warning,
            "checked_layers": self.checked_layers,
        }


def check_deliverable_fields(artifact_type: ArtifactType, content: dict) -> list[str]:
    """按 artifact_type 的必填字段做结构校验 (复用 gate.py 的占位符黑名单口径)。"""
    required = DELIVERABLE_REQUIRED_FIELDS.get(artifact_type.value, [])
    gaps: list[str] = []
    for name in required:
        value = content.get(name)
        if value is None:
            gaps.append(f"缺少必填字段「{name}」")
        elif isinstance(value, str) and (
            not value.strip() or value.strip() in _PLACEHOLDER_VALUES
        ):
            gaps.append(f"字段「{name}」内容为空或占位符")
        elif isinstance(value, list) and len(value) == 0:
            gaps.append(f"字段「{name}」列表为空")
    return gaps


def _phase_for(artifact_type: ArtifactType) -> PhaseType | None:
    for pt, atypes in PHASE_ARTIFACT_MAP.items():
        if artifact_type in atypes:
            return pt
    return None


async def evaluate_conversation_gate(
    artifact_type: ArtifactType,
    content: dict,
    *,
    constraint: ProcessConstraint,
    prior_artifacts: dict | None = None,
    conventions: str = "",
    charter: str = "",
    llm_review_fn=None,
) -> ConversationGateResult:
    """对话模式质量门禁评估，按 GateProfile 分级。

    4 层评估: 结构校验 (必跑) → 方法论 (主产物+启用时) → 交叉一致性 (主产物+启用时)
              → LLM 评审 (启用且结构缺口未短路时)。
    结构缺口≥short_circuit 直接判失败，省 LLM 成本。
    charter/conventions 在 LLM 评审层注入, 评判产出是否符合项目宪章治理意图 + 用户规范。
    llm_review_fn 可注入用于测试；None 用默认 resilient adapter。
    """
    profile = get_profile(constraint)
    prior_artifacts = prior_artifacts or {}
    checked: list[str] = ["structural"]

    phase_type = _phase_for(artifact_type)
    if not phase_type:
        # 未知 artifact 类型，无法判定 phase，放行 (无质量信号而非误杀)
        return ConversationGateResult(
            passed=True, score=8, threshold=profile.score_threshold,
            checked_layers=checked,
        )

    is_primary = PHASE_PRIMARY_ARTIFACT.get(phase_type) == artifact_type

    # 层 1: 结构校验 (artifact 粒度)
    gaps = check_deliverable_fields(artifact_type, content)

    # 层 2: 方法论校验 (仅 phase 主产物，复用 gate.py)
    if profile.enable_methodology and is_primary:
        checked.append("methodology")
        gaps.extend(await _safe_methodology(phase_type, content))

    # 层 3: 交叉一致性 (仅 phase 主产物且有前置)
    if profile.enable_cross_check and is_primary and prior_artifacts:
        checked.append("cross_check")
        gaps.extend(_safe_cross_consistency(phase_type, content, prior_artifacts))

    # 结构缺口短路: 缺口过多直接失败，不调 LLM
    if len(gaps) >= profile.structural_short_circuit:
        return ConversationGateResult(
            passed=False, score=2, gaps=gaps,
            suggestion="产出物缺少多个关键字段，请补全后再提交。",
            threshold=profile.score_threshold, checked_layers=checked,
        )

    # 层 4: LLM 质量评审
    score = 8
    llm_gaps: list[str] = []
    suggestion = ""
    if profile.enable_llm_review:
        checked.append("llm_review")
        score, llm_gaps, suggestion = await _run_llm_review(
            phase_type, content, conventions, charter, llm_review_fn,
        )

    all_gaps = list(dict.fromkeys(gaps + llm_gaps))  # 去重保序
    passed = (len(gaps) == 0) and score >= profile.score_threshold

    return ConversationGateResult(
        passed=passed, score=score, gaps=all_gaps,
        suggestion=suggestion or (
            "质量达标，可进入下一步。" if passed else "请补充完善产出物。"
        ),
        threshold=profile.score_threshold, checked_layers=checked,
    )


async def _safe_methodology(phase_type: PhaseType, content: dict) -> list[str]:
    """防御性调用 gate._check_methodology — 字段错配时降级为空 (不阻断)。"""
    try:
        from arc.application.pipeline.gate import _check_methodology

        return await _check_methodology(phase_type, content)
    except Exception as exc:
        logger.debug("methodology check skipped for %s: %s", phase_type, exc)
        return []


def _safe_cross_consistency(
    phase_type: PhaseType, content: dict, prior_artifacts: dict
) -> list[str]:
    """防御性调用 gate._check_cross_consistency。"""
    try:
        from arc.application.pipeline.gate import _check_cross_consistency

        return _check_cross_consistency(phase_type, content, prior_artifacts)
    except Exception as exc:
        logger.debug("cross-consistency check skipped for %s: %s", phase_type, exc)
        return []


async def _run_llm_review(phase_type, content, conventions, charter, llm_review_fn):
    """执行 LLM 质量评审，返回 (score, gaps, suggestion)。

    charter (系统生成治理底座) + conventions (用户增量) 均注入, 评判产出是否符合
    项目宪章治理意图与用户规范。两者为空则对应 section 省略 (不污染 prompt)。
    """
    from arc.application.pipeline.gate import PHASE_LABELS
    from arc.application.pipeline.prompts import GATE_EVALUATION_PROMPT

    phase_label = PHASE_LABELS.get(phase_type, phase_type.value)
    conventions_section = (
        f"\n## 项目规范（产出物必须符合）:\n{conventions}\n"
        if conventions.strip() else ""
    )
    charter_section = (
        "\n## 项目宪章 (系统生成·按项目类型, 产出必须符合治理意图):\n"
        f"{charter}\n"
        if charter.strip() else ""
    )
    prompt = GATE_EVALUATION_PROMPT.format(
        phase_label=phase_label,
        artifact_content=json.dumps(content, ensure_ascii=False, indent=2),
        charter_section=charter_section,
        conventions_section=conventions_section,
    )

    if llm_review_fn is not None:
        result_data = await llm_review_fn(prompt)
    else:
        result_data = await _default_llm_review(prompt)

    if not isinstance(result_data, dict):
        logger.warning("conversation gate LLM review parse failed")
        return 8, [], ""  # 解析失败保守给通过分，结构校验已兜底
    return (
        int(result_data.get("score", 8)),
        list(result_data.get("gaps", []) or []),
        str(result_data.get("suggestion", "")),
    )


async def _default_llm_review(prompt: str) -> dict:
    """默认 LLM 评审实现 (复用 resilient adapter)。"""
    from arc.application.ai.json_extract import extract_json
    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.ai.resilience import create_resilient_adapter

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat([LLMMessage(role="user", content=prompt)])
    finally:
        await adapter.close()
    return extract_json(response.content)

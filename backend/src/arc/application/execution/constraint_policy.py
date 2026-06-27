"""过程约束策略分发器 — 根据 ProcessConstraint 决定方法论 prompt 深度。

T8 清理 (v6.0): ConstraintPolicy 原有 11 字段中 10 个零引用——门禁职责
(阈值/交叉检查/依赖阻断/确认/充分性) 已由 content.gate.GateProfile 接管。
本模块精简为仅保留 methodology_depth, 驱动 get_methodology_prompt_for_constraint。

| 维度 | strict | moderate | free |
|------|--------|----------|------|
| 方法论深度 | 完整流程 (全部子步骤) | 精简流程 (核心步骤) | 最轻量 (质量底线) |
| 门禁严格度 | (见 content.gate.GateProfile, score≥7) | (score≥6) | (score≥5) |

方法论语料仍按 phase 分发 (clarification/ui_design/architecture/development/testing)。
"""

from __future__ import annotations

from dataclasses import dataclass

from arc.application.context.content.methodology import FREE_BASELINES, MODERATE_PROMPTS
from arc.domain.project.value_objects import ProcessConstraint


@dataclass(frozen=True)
class ConstraintPolicy:
    """某个 constraint 级别下的方法论深度策略。

    T8 后仅保留 methodology_depth — get_methodology_prompt_for_constraint 的唯一消费字段。
    门禁/交叉检查/确认等行为参数见 content.gate.GateProfile。
    """

    methodology_depth: str  # "full" | "core" | "minimal"


# 三级策略定义 (门禁参数已移至 content.gate.PROFILES)
CONSTRAINT_POLICIES: dict[ProcessConstraint, ConstraintPolicy] = {
    ProcessConstraint.STRICT: ConstraintPolicy(methodology_depth="full"),
    ProcessConstraint.MODERATE: ConstraintPolicy(methodology_depth="core"),
    ProcessConstraint.FREE: ConstraintPolicy(methodology_depth="minimal"),
}


def get_policy(constraint: ProcessConstraint) -> ConstraintPolicy:
    return CONSTRAINT_POLICIES.get(constraint, CONSTRAINT_POLICIES[ProcessConstraint.FREE])


# ---------------------------------------------------------------------------
# 方法论 prompt 深度控制
# ---------------------------------------------------------------------------


def get_methodology_prompt_for_constraint(
    constraint: ProcessConstraint,
    phase: str,
    conversation_round: int,
    *,
    title: str = "",
    description: str = "",
) -> str:
    """根据 constraint 级别返回不同深度的方法论 prompt。

    - strict: 完整流程，逐步引导
    - moderate: 核心要点，一次性给出
    - free: 质量底线提示（不引导方法论步骤，但明确产出物质量标准）

    Args:
        title/description: 需求标题与描述, 供 clarification strict 模式的
            route_strategy 做关键词路由(NEW_DOMAIN/OPTIMIZATION)。
    """
    policy = get_policy(constraint)

    if policy.methodology_depth == "minimal":
        return _quality_baseline_prompt(phase)  # free 模式: 质量底线

    if phase == "clarification":
        return _clarification_prompt(policy, conversation_round, title, description)
    if phase == "ui_design":
        return _ui_design_prompt(policy, conversation_round)
    if phase == "architecture":
        return _architecture_prompt(policy, conversation_round)
    if phase == "development":
        return _development_prompt(policy)
    if phase == "testing":
        return _testing_prompt(policy)

    return ""


def _quality_baseline_prompt(phase: str) -> str:
    """自由模式的质量底线 — 不约束怎么做，但明确做到什么标准才算完。"""
    return FREE_BASELINES.get(phase, "")


def _clarification_prompt(
    policy: ConstraintPolicy, round: int, title: str, description: str
) -> str:
    if policy.methodology_depth == "full":
        # strict: 完整三策略递进
        from arc.application.execution.clarification_strategy import (
            build_clarification_prompt,
            route_strategy,
        )
        strategy = route_strategy(title, description, round)
        return build_clarification_prompt(strategy, round)
    else:
        # moderate: 直接给六维框架，不做策略路由
        return MODERATE_PROMPTS["clarification"]


def _ui_design_prompt(policy: ConstraintPolicy, round: int) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.ui_design_methodology import get_ui_design_prompt
        return get_ui_design_prompt(round)
    else:
        return MODERATE_PROMPTS["ui_design"]


def _architecture_prompt(policy: ConstraintPolicy, round: int) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.architecture_methodology import (
            get_methodology_overview,
            get_sub_phase_prompt,
        )
        return f"{get_methodology_overview()}\n\n{get_sub_phase_prompt(round)}"
    else:
        return MODERATE_PROMPTS["architecture"]


def _development_prompt(policy: ConstraintPolicy) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.dev_test_methodology import get_development_prompt
        return get_development_prompt(0)
    else:
        return MODERATE_PROMPTS["development"]


def _testing_prompt(policy: ConstraintPolicy) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.dev_test_methodology import get_testing_prompt
        return get_testing_prompt(0)
    else:
        return MODERATE_PROMPTS["testing"]

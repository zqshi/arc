"""过程约束策略分发器 — 根据 ProcessConstraint 决定方法论 prompt 深度。

T8 清理 (v6.0): ConstraintPolicy 原有 11 字段中 10 个零引用——门禁职责
(阈值/交叉检查/依赖阻断/确认/充分性) 已由 gate_threshold.GateProfile 接管。
本模块精简为仅保留 methodology_depth, 驱动 get_methodology_prompt_for_constraint。

| 维度 | strict | moderate | free |
|------|--------|----------|------|
| 方法论深度 | 完整流程 (全部子步骤) | 精简流程 (核心步骤) | 最轻量 (质量底线) |
| 门禁严格度 | (见 gate_threshold.GateProfile, score≥7) | (score≥6) | (score≥5) |

方法论语料仍按 phase 分发 (clarification/ui_design/architecture/development/testing)。
"""

from __future__ import annotations

from dataclasses import dataclass

from arc.domain.project.value_objects import ProcessConstraint


@dataclass(frozen=True)
class ConstraintPolicy:
    """某个 constraint 级别下的方法论深度策略。

    T8 后仅保留 methodology_depth — get_methodology_prompt_for_constraint 的唯一消费字段。
    门禁/交叉检查/确认等行为参数见 gate_threshold.GateProfile。
    """

    methodology_depth: str  # "full" | "core" | "minimal"


# 三级策略定义 (门禁参数已移至 gate_threshold.PROFILES)
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
) -> str:
    """根据 constraint 级别返回不同深度的方法论 prompt。

    - strict: 完整流程，逐步引导
    - moderate: 核心要点，一次性给出
    - free: 质量底线提示（不引导方法论步骤，但明确产出物质量标准）
    """
    policy = get_policy(constraint)

    if policy.methodology_depth == "minimal":
        return _quality_baseline_prompt(phase)  # free 模式: 质量底线

    if phase == "clarification":
        return _clarification_prompt(policy, conversation_round)
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
    baselines = {
        "clarification": """\
## 质量底线
产出 requirement_spec 时，以下字段不得为空或占位：
- target_users（至少 1 个具体角色）
- user_stories（至少覆盖核心场景）
- acceptance_criteria（每个 P0 story 至少 1 条 AC）
- boundaries.in_scope + out_of_scope""",

        "ui_design": """\
## 质量底线
产出 interaction_design 时：
- user_flows 每个流程有完整 mermaid 流程图
- page_map 标注页面间跳转关系
- 至少定义空状态和加载态

产出 ui_spec 时：
- design_tokens 必须包含 colors + typography + spacing
- component_specs 每个组件有 states 描述和尺寸规范

产出 prototype 时：
- pages 每页有完整可渲染 HTML（含 Tailwind）
- 标注对应用户场景
- 核心操作路径 ≤ 3 步可达""",

        "architecture": """\
## 质量底线
产出 tech_architecture 时：
- tech_decisions 每个决策必须有 ≥2 个候选方案
- data_model.entities 与 user_stories 对齐
- 不得有上下文间循环依赖""",

        "development": """\
## 质量底线
产出 dev_report 时：
- test_results 不得包含 FAIL/ERROR
- code_changes 不得为空""",

        "testing": """\
## 质量底线
产出 test_report 时：
- criteria_verification 逐条覆盖 P0 验收标准
- 每个 pass 必须有 evidence（不接受无证据的自述）""",

        "deployment": """\
## 质量底线
产出 deploy_report 时：
- deploy_log.steps_executed 每步有明确 status
- health_check_result 至少检查一个关键端点
- rollback_plan 不得为空""",

        "extraction": """\
## 质量底线
产出 experience_card 时：
- problem + solution 不得为占位文本
- decisions 至少包含 1 个有 options_considered 的决策点
- pitfalls 记录至少 1 个实际遇到的问题""",
    }
    return baselines.get(phase, "")


def _clarification_prompt(policy: ConstraintPolicy, round: int) -> str:
    if policy.methodology_depth == "full":
        # strict: 完整三策略递进
        from arc.application.execution.clarification_strategy import (
            build_clarification_prompt,
            route_strategy,
        )
        strategy = route_strategy("", "", round)
        return build_clarification_prompt(strategy, round)
    else:
        # moderate: 直接给六维框架，不做策略路由
        return """\
## 需求澄清（精简模式）

快速确认以下六项，有答案即可产出：
1. **目标用户** — 谁在用？
2. **使用场景** — 什么情境触发？
3. **核心痛点** — 当前怎么解决的？为什么不够好？
4. **功能方向** — 大致做什么？
5. **边界** — 明确不做什么？
6. **成功标准** — 做到什么程度算完？

信息足够时直接产出交付物，不必追问到完美。"""


def _ui_design_prompt(policy: ConstraintPolicy, round: int) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.ui_design_methodology import get_ui_design_prompt
        return get_ui_design_prompt(round)
    else:
        return """\
## 交互设计（精简模式）

产出 wireframe 时注意：
- 每页标注对应的用户场景
- 定义空状态和加载态
- 核心操作路径 ≤ 3 步"""


def _architecture_prompt(policy: ConstraintPolicy, round: int) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.architecture_methodology import (
            get_methodology_overview,
            get_sub_phase_prompt,
        )
        return f"{get_methodology_overview()}\n\n{get_sub_phase_prompt(round)}"
    else:
        return """\
## 技术架构（精简模式）

产出时确保：
- 每个技术决策有 ≥2 个候选方案 + 选择理由
- 数据模型与需求中的用户故事对齐
- API 设计覆盖核心场景"""


def _development_prompt(policy: ConstraintPolicy) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.dev_test_methodology import get_development_prompt
        return get_development_prompt(0)
    else:
        return """\
## 开发（精简模式）

建议测试优先，但不强制 TDD 循环。完成前确认测试通过。"""


def _testing_prompt(policy: ConstraintPolicy) -> str:
    if policy.methodology_depth == "full":
        from arc.application.execution.dev_test_methodology import get_testing_prompt
        return get_testing_prompt(0)
    else:
        return """\
## 测试（精简模式）

逐条对照验收标准，每条 pass/fail 需有证据。"""

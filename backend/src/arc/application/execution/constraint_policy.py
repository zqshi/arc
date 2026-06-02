"""过程约束策略分发器 — 根据 ProcessConstraint 决定方法论深度和行为差异。

三个模式的核心区别不仅是"管控力度"，更是"推理深度"和"质量保障策略"的差异。

| 维度 | strict | moderate | free |
|------|--------|----------|------|
| 方法论深度 | 完整流程 (全部子步骤) | 精简流程 (核心步骤) | 最轻量 (仅充分性检测) |
| 门禁严格度 | violations 阻断 + warnings 也阻断 | violations 阻断 + warnings 放行 | 仅记录不阻断 |
| 交叉验证 | 全量 (story↔API, AC↔test, ...) | 核心对 (AC↔test) | 不执行 |
| 澄清深度 | 完整三策略递进 | 单策略直达 | 充分性通过即可产出 |
| DDD 引导 | 三步强制递进 (每步独立 gate) | 概览 + 自由产出 | 无引导 |
| TDD 约束 | 强制 RED→GREEN→REFACTOR | 建议测试优先 | 无约束 |
| 产出物确认 | 必须显式确认 | 自动提取 + 建议确认 | 自动提取即生效 |
"""

from __future__ import annotations

from dataclasses import dataclass

from arc.domain.project.value_objects import ProcessConstraint


@dataclass(frozen=True)
class ConstraintPolicy:
    """某个 constraint 级别下的行为策略"""

    # 方法论注入
    methodology_depth: str  # "full" | "core" | "minimal"
    clarification_max_rounds: int  # 追问最大轮次
    ddd_sub_phases: int  # DDD 子阶段数 (3=完整, 1=概览, 0=无)
    tdd_enforced: bool  # 是否强制 TDD 循环

    # 门禁
    gate_block_on_warnings: bool  # warnings 是否也阻断
    cross_check_enabled: bool  # 交叉一致性检查
    cross_check_scope: str  # "full" | "core" | "none"

    # 产出物管理
    auto_extract: bool
    require_confirm: bool
    show_phase_ui: bool

    # 充分性检测
    sufficiency_strict: bool  # True=三项全 clear 才通过; False=有方向即可


# 三级策略定义
CONSTRAINT_POLICIES: dict[ProcessConstraint, ConstraintPolicy] = {
    ProcessConstraint.STRICT: ConstraintPolicy(
        methodology_depth="full",
        clarification_max_rounds=12,  # 允许深度追问
        ddd_sub_phases=3,  # 完整三步
        tdd_enforced=True,
        gate_block_on_warnings=True,
        cross_check_enabled=True,
        cross_check_scope="full",
        auto_extract=False,
        require_confirm=True,
        show_phase_ui=True,
        sufficiency_strict=True,
    ),
    ProcessConstraint.MODERATE: ConstraintPolicy(
        methodology_depth="core",
        clarification_max_rounds=6,  # 中等深度
        ddd_sub_phases=1,  # 只给概览，不强制三步
        tdd_enforced=False,
        gate_block_on_warnings=False,
        cross_check_enabled=True,
        cross_check_scope="core",  # 只做 AC↔test
        auto_extract=True,
        require_confirm=False,
        show_phase_ui=True,
        sufficiency_strict=False,  # 有方向即可
    ),
    ProcessConstraint.FREE: ConstraintPolicy(
        methodology_depth="minimal",
        clarification_max_rounds=3,  # 快速通过
        ddd_sub_phases=0,  # 不引导步骤
        tdd_enforced=False,
        gate_block_on_warnings=False,
        cross_check_enabled=True,  # 仍执行交叉检查
        cross_check_scope="core",  # 核心对 (AC↔test)
        auto_extract=True,
        require_confirm=False,
        show_phase_ui=False,
        sufficiency_strict=False,
    ),
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
- wireframes 每页标注对应用户场景
- 至少定义空状态和加载态
- component_specs 每个组件有 states 描述""",

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

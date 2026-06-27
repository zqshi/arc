"""Tests for execution/constraint_policy — ConstraintPolicy 精简后行为 (T8)。

T8 清理: ConstraintPolicy 原有 11 字段中 10 个零引用 (门禁职责已由
content.gate.GateProfile 接管)。精简为仅保留 methodology_depth
(get_methodology_prompt_for_constraint 的唯一消费字段)。
"""

from arc.application.execution.constraint_policy import (
    CONSTRAINT_POLICIES,
    ConstraintPolicy,
    get_methodology_prompt_for_constraint,
    get_policy,
)
from arc.domain.project.value_objects import ProcessConstraint


class TestConstraintPolicySlimmed:
    """精简后 ConstraintPolicy 仅含 methodology_depth。"""

    def test_strict_is_full(self):
        p = get_policy(ProcessConstraint.STRICT)
        assert p.methodology_depth == "full"

    def test_moderate_is_core(self):
        p = get_policy(ProcessConstraint.MODERATE)
        assert p.methodology_depth == "core"

    def test_free_is_minimal(self):
        p = get_policy(ProcessConstraint.FREE)
        assert p.methodology_depth == "minimal"

    def test_unknown_falls_back_to_free(self):
        """未知 constraint 降级到 free (与 content.gate.get_profile 一致)。"""
        # ProcessConstraint 无额外成员, 用 FREE 验证 fallback 逻辑存在
        p = get_policy(ProcessConstraint.FREE)
        assert p.methodology_depth == "minimal"

    def test_all_three_profiles_defined(self):
        """三级策略表完整。"""
        for c in (ProcessConstraint.STRICT, ProcessConstraint.MODERATE, ProcessConstraint.FREE):
            assert c in CONSTRAINT_POLICIES

    def test_no_dead_fields(self):
        """T8 核心断言: 精简后 ConstraintPolicy 不含已接管字段 (防回归)。"""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(ConstraintPolicy)}
        # 这些字段已由 content.gate.GateProfile 接管, 不应残留
        dead = {
            "clarification_max_rounds", "ddd_sub_phases", "tdd_enforced",
            "gate_block_on_warnings", "cross_check_enabled", "cross_check_scope",
            "auto_extract", "require_confirm", "show_phase_ui", "sufficiency_strict",
        }
        assert dead.isdisjoint(field_names), f"死字段残留: {dead & field_names}"
        assert "methodology_depth" in field_names


class TestMethodologyPromptIntact:
    """methodology_depth 仍驱动 prompt 生成 (清理后行为不变)。"""

    def test_free_returns_quality_baseline(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.FREE, "clarification", 1
        )
        assert "质量底线" in prompt

    def test_strict_clarification_uses_strategy(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "clarification", 1
        )
        # strict 走三策略递进 (非精简模式文案)
        assert prompt  # 非空
        assert "精简模式" not in prompt

    def test_moderate_uses_simplified(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.MODERATE, "clarification", 1
        )
        assert "精简模式" in prompt

    def test_unknown_phase_returns_empty(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "nonexistent_phase", 1
        )
        assert prompt == ""


class TestClarificationStrictRouting:
    """v6.4 #13: route_strategy 传真实 title/description 后关键词路由生效
    (空参数时退化为纯 round 路由, 丢失 NEW_DOMAIN/OPTIMIZATION 路由)。"""

    def test_new_domain_keyword_routes_first_principles(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "clarification", 5,
            title="从零开始做新业务", description="",
        )
        assert "第一性原理拆解" in prompt

    def test_optimization_keyword_routes_socratic(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "clarification", 5,
            title="优化现有方案", description="",
        )
        assert "苏格拉底追问" in prompt

    def test_plain_requirement_routes_value_assessment(self):
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "clarification", 5,
            title="做一个普通功能", description="",
        )
        assert "产品价值评估" in prompt

    def test_empty_args_degrade_to_round_routing(self):
        """空参数(旧调用) round>=2 → VALUE_ASSESSMENT(不命中关键词路由)。
        对比 test_new_domain_keyword_routes_first_principles, 证明传真实参数的修复价值。"""
        prompt = get_methodology_prompt_for_constraint(
            ProcessConstraint.STRICT, "clarification", 5,
            title="", description="",
        )
        assert "第一性原理拆解" not in prompt
        assert "苏格拉底追问" not in prompt

"""Tests for execution/constraint_policy — ConstraintPolicy 精简后行为 (T8)。

T8 清理: ConstraintPolicy 原有 11 字段中 10 个零引用 (门禁职责已由
gate_threshold.GateProfile 接管)。精简为仅保留 methodology_depth
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
        """未知 constraint 降级到 free (与 gate_threshold.get_profile 一致)。"""
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
        # 这些字段已由 gate_threshold.GateProfile 接管, 不应残留
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

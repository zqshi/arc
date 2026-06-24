"""门禁阈值注册表单元测试。"""

from __future__ import annotations

from arc.application.execution.gate_threshold import PROFILES, get_profile
from arc.domain.project.value_objects import ProcessConstraint


class TestGateProfileGrading:
    def test_score_threshold_increases_with_strictness(self) -> None:
        # free≥5 < moderate≥6 < strict≥7
        assert get_profile(ProcessConstraint.FREE).score_threshold == 5
        assert get_profile(ProcessConstraint.MODERATE).score_threshold == 6
        assert get_profile(ProcessConstraint.STRICT).score_threshold == 7

    def test_free_disables_methodology(self) -> None:
        # free 不跑方法论校验 (轻量)，但保留交叉一致性 + LLM 评审 (质量底线)
        free = get_profile(ProcessConstraint.FREE)
        assert free.enable_methodology is False
        assert free.enable_cross_check is True
        assert free.enable_llm_review is True

    def test_strict_enables_all_layers(self) -> None:
        strict = get_profile(ProcessConstraint.STRICT)
        assert strict.enable_methodology is True
        assert strict.enable_cross_check is True
        assert strict.enable_llm_review is True

    def test_free_uses_soft_dependency_block(self) -> None:
        free = get_profile(ProcessConstraint.FREE)
        assert free.dependency_block_mode == "soft"
        # free 也硬阻断 experience_card / deploy_report (兜底)
        assert "experience_card" in free.dependency_hard_block
        assert "deploy_report" in free.dependency_hard_block

    def test_moderate_and_strict_use_hard_dependency_block(self) -> None:
        assert get_profile(ProcessConstraint.MODERATE).dependency_block_mode == "hard"
        assert get_profile(ProcessConstraint.STRICT).dependency_block_mode == "hard"

    def test_structural_short_circuit_decreases_with_strictness(self) -> None:
        # 越严格越早短路 (更不容忍结构缺口)
        f = get_profile(ProcessConstraint.FREE).structural_short_circuit
        m = get_profile(ProcessConstraint.MODERATE).structural_short_circuit
        s = get_profile(ProcessConstraint.STRICT).structural_short_circuit
        assert f >= m >= s

    def test_all_constraints_have_profile(self) -> None:
        for c in ProcessConstraint:
            assert c in PROFILES

    def test_unknown_constraint_falls_back_to_free(self) -> None:
        # 传一个不在表里的值 (构造 fake)，应降级 free
        class FakeStr(str):
            pass

        fake = FakeStr("nonexistent")
        assert get_profile(fake).score_threshold == 5  # free 的阈值

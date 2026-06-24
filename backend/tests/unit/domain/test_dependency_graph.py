"""交付物依赖图单元测试。"""

from __future__ import annotations

from arc.domain.planning.dependency_graph import (
    DELIVERABLE_DEPENDENCIES,
    missing_prerequisites,
)


class TestMissingPrerequisites:
    def test_root_has_no_prerequisites(self) -> None:
        assert missing_prerequisites("requirement_spec", set()) == []

    def test_direct_dependency_missing(self) -> None:
        # tech_architecture 依赖 requirement_spec，缺失时返回它
        result = missing_prerequisites("tech_architecture", set())
        assert result == ["requirement_spec"]

    def test_direct_dependency_satisfied(self) -> None:
        result = missing_prerequisites("tech_architecture", {"requirement_spec"})
        assert result == []

    def test_multiple_dependencies_partial(self) -> None:
        # deploy_report 依赖 dev_report + app_code + test_report，部分缺失
        result = missing_prerequisites(
            "deploy_report", {"dev_report", "test_report"}
        )
        assert result == ["app_code"]

    def test_multiple_dependencies_all_missing(self) -> None:
        result = missing_prerequisites("deploy_report", set())
        assert result == ["dev_report", "app_code", "test_report"]

    def test_preserves_declaration_order(self) -> None:
        # ui_spec 依赖 [requirement_spec, interaction_design]，全缺失时按声明顺序
        result = missing_prerequisites("ui_spec", set())
        assert result == ["requirement_spec", "interaction_design"]

    def test_unknown_target_returns_empty(self) -> None:
        # 未知 target 不阻断 (质量门禁兜底)
        assert missing_prerequisites("nonexistent_type", set()) == []

    def test_all_known_deliverables_have_entry(self) -> None:
        # 所有 plan 中提到的交付物都必须在图里有显式声明 (含空列表)
        expected = {
            "requirement_spec", "interaction_design", "ui_spec", "prototype",
            "tech_architecture", "service_spec", "dev_report", "app_code",
            "test_report", "deploy_report", "experience_card",
        }
        assert set(DELIVERABLE_DEPENDENCIES.keys()) == expected

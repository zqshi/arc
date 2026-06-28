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
        # tech_architecture 依赖 requirement_spec + prototype, 全缺时按声明顺序返回
        result = missing_prerequisites("tech_architecture", set())
        assert result == ["requirement_spec", "prototype"]

    def test_direct_dependency_satisfied(self) -> None:
        # 前置全达标才返回空 (仅 requirement_spec 不够, 还需 prototype)
        result = missing_prerequisites(
            "tech_architecture", {"requirement_spec", "prototype"}
        )
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

    def test_prototype_required_by_architecture_and_app_code(self) -> None:
        # v6.15: tech_architecture 与 app_code 均依赖 prototype
        # 堵"没原型就写代码"——缺 prototype 时两者都不可产出
        result = missing_prerequisites("app_code", {"tech_architecture", "service_spec"})
        assert result == ["prototype"]

    def test_app_code_required_by_dev_report_and_test_report(self) -> None:
        # v6.15: dev_report/test_report 依赖 app_code
        # 堵"没代码就报告/没代码就测试"
        dev_missing = missing_prerequisites(
            "dev_report", {"tech_architecture", "service_spec"}
        )
        assert dev_missing == ["app_code"]
        test_missing = missing_prerequisites(
            "test_report", {"requirement_spec", "tech_architecture"}
        )
        assert test_missing == ["app_code"]

    def test_experience_card_requires_dev_report(self) -> None:
        # v6.15: 经验卡依赖 requirement_spec + dev_report
        # 有实现沉淀才能提炼, 不强制部署链完整
        result = missing_prerequisites("experience_card", {"requirement_spec"})
        assert result == ["dev_report"]

    def test_all_known_deliverables_have_entry(self) -> None:
        # 所有 plan 中提到的交付物都必须在图里有显式声明 (含空列表)
        expected = {
            "requirement_spec", "interaction_design", "ui_spec", "prototype",
            "tech_architecture", "service_spec", "dev_report", "app_code",
            "test_report", "deploy_report", "experience_card",
        }
        assert set(DELIVERABLE_DEPENDENCIES.keys()) == expected

    def test_graph_is_acyclic(self) -> None:
        # v6.15: 依赖图必须是合法 DAG (无环) —— 依赖守卫基于"前置可逐个解锁",
        # 出现环则某些交付物永远无法满足前置, 整条链死锁。改图时不得引入环。
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {n: WHITE for n in DELIVERABLE_DEPENDENCIES}

        def has_cycle(node: str) -> bool:
            color[node] = GRAY
            for dep in DELIVERABLE_DEPENDENCIES[node]:
                # 指向图中不存在的节点 = 声明错误, 单独报
                assert dep in color, f"未知前置 {dep!r} (被 {node!r} 依赖)"
                if color[dep] == GRAY:
                    return True  # 回到正在访问的节点 = 环
                if color[dep] == WHITE and has_cycle(dep):
                    return True
            color[node] = BLACK
            return False

        for node in DELIVERABLE_DEPENDENCIES:
            if color[node] == WHITE:
                assert not has_cycle(node), "DELIVERABLE_DEPENDENCIES 存在环"

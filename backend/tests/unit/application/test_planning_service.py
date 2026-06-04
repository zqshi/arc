from __future__ import annotations

from unittest.mock import MagicMock

from arc.application.planning.planning_service import (
    PlanningService,
    _feature_key,
)


class TestFeatureKey:
    def test_basic(self) -> None:
        assert _feature_key("User Login") == "user login"

    def test_strips_whitespace(self) -> None:
        assert _feature_key("  Auth  ") == "auth"

    def test_truncates_long_title(self) -> None:
        long_title = "x" * 300
        assert len(_feature_key(long_title)) == 200


class TestFormatConstraints:
    def test_empty(self) -> None:
        result = PlanningService._format_constraints({})
        assert "无特定约束" in result

    def test_with_team_and_iteration(self) -> None:
        result = PlanningService._format_constraints({
            "team_capacity": 5,
            "iteration_weeks": 2,
        })
        assert "5人" in result
        assert "2周" in result

    def test_with_deadlines(self) -> None:
        result = PlanningService._format_constraints({
            "hard_deadlines": ["2026-06-01", "2026-09-01"],
        })
        assert "2026-06-01" in result
        assert "2026-09-01" in result

    def test_with_strategy(self) -> None:
        result = PlanningService._format_constraints({
            "release_strategy": "MVP优先",
            "priority_framework": "MoSCoW",
        })
        assert "MVP优先" in result
        assert "MoSCoW" in result


class TestFormatTodoStatus:
    def test_empty(self) -> None:
        from arc.application.planning.analysis_service import AnalysisService
        result = AnalysisService._format_todo_status([])
        assert "无需求" in result

    def test_with_todos(self) -> None:
        from arc.application.planning.analysis_service import AnalysisService

        t1 = MagicMock()
        t1.id = "id1"
        t1.status.value = "pending"
        t1.title = "登录功能"
        t1.description = ""

        t2 = MagicMock()
        t2.id = "id2"
        t2.status.value = "active"
        t2.title = "注册功能"
        t2.description = "用户注册"

        result = AnalysisService._format_todo_status([t1, t2])
        assert "pending" in result
        assert "登录功能" in result
        assert "active" in result


class TestExtractAllFeaturesFromData:
    def test_from_versions(self) -> None:
        data = [
            {"name": "v1.0", "features": [{"title": "A"}, {"title": "B"}]},
            {"name": "v2.0", "features": [{"title": "C"}]},
        ]
        result = PlanningService._extract_all_features_from_data(data)
        assert len(result) == 3

    def test_flat_list_fallback(self) -> None:
        data = [{"title": "X"}, {"title": "Y"}]
        result = PlanningService._extract_all_features_from_data(data)
        assert len(result) == 2

    def test_empty(self) -> None:
        result = PlanningService._extract_all_features_from_data([])
        assert result == []

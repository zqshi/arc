"""Unit tests for PromptBuilder — tests the pure/testable parts."""

from __future__ import annotations

from arc.application.context.prompt_builder import PromptBuilder


class TestBuildDeliverableSection:
    def test_all_pending(self) -> None:
        result = PromptBuilder._build_deliverable_section(
            required=["requirement_spec", "tech_architecture"],
            completed=[],
        )
        assert "requirement_spec" in result
        assert "tech_architecture" in result
        assert "[ ]" in result  # unchecked

    def test_some_completed(self) -> None:
        result = PromptBuilder._build_deliverable_section(
            required=["requirement_spec", "tech_architecture"],
            completed=["requirement_spec"],
        )
        assert "[x]" in result  # checked
        # Schema only shown for uncompleted
        assert "tech_architecture" in result

    def test_all_completed(self) -> None:
        result = PromptBuilder._build_deliverable_section(
            required=["requirement_spec"],
            completed=["requirement_spec"],
        )
        assert "[x]" in result

    def test_empty_required(self) -> None:
        result = PromptBuilder._build_deliverable_section(
            required=[],
            completed=[],
        )
        assert "交付物清单" in result

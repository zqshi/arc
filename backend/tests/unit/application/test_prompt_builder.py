"""Unit tests for prompt/context building — tests the pure/testable parts."""

from __future__ import annotations

from arc.application.context.prompts import (
    ARTIFACT_SCHEMAS,
    build_deliverable_checklist,
)
from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType


def _build_deliverable_section(required: list[str], completed: list[str]) -> str:
    """Test helper — mirrors the logic from DeliverableProvider."""
    checklist = build_deliverable_checklist(required, completed)
    schemas = "\n".join(
        f"- **{ARTIFACT_LABELS.get(ArtifactType(t), t)}** (`{t}`):"
        f"\n```\n{ARTIFACT_SCHEMAS.get(t, '{}')}\n```"
        for t in required
        if t not in completed
    )
    return (
        f"## 交付物清单（渐进式完成）\n{checklist}\n\n"
        "## 交付物输出规则\n"
        "当你认为某个交付物内容已经充分时，使用以下格式输出：\n\n"
        "[DELIVERABLE:artifact_type]\n```json\n(结构化内容)\n```\n\n"
        f"可用的artifact_type及其schema：\n{schemas}"
    )


class TestBuildDeliverableSection:
    def test_all_pending(self) -> None:
        result = _build_deliverable_section(
            required=["requirement_spec", "tech_architecture"],
            completed=[],
        )
        assert "requirement_spec" in result
        assert "tech_architecture" in result
        assert "[ ]" in result  # unchecked

    def test_some_completed(self) -> None:
        result = _build_deliverable_section(
            required=["requirement_spec", "tech_architecture"],
            completed=["requirement_spec"],
        )
        assert "[x]" in result  # checked
        # Schema only shown for uncompleted
        assert "tech_architecture" in result

    def test_all_completed(self) -> None:
        result = _build_deliverable_section(
            required=["requirement_spec"],
            completed=["requirement_spec"],
        )
        assert "[x]" in result

    def test_empty_required(self) -> None:
        result = _build_deliverable_section(
            required=[],
            completed=[],
        )
        assert "交付物清单" in result


class TestContextProtocol:
    """Test ContextSegment and budget logic."""

    def test_segment_auto_estimates_tokens(self) -> None:
        from arc.application.context.protocol import ContextSegment

        seg = ContextSegment(
            source="test",
            priority=1,
            content="Hello world, this is a test.",
        )
        assert seg.token_estimate > 0

    def test_phase_budget_lookup(self) -> None:
        from arc.application.context.protocol import get_source_budget

        # Architecture phase should give domain_model more budget
        arch_dm = get_source_budget("architecture", "domain_model")
        clar_dm = get_source_budget("clarification", "domain_model")
        assert arch_dm > clar_dm

    def test_unknown_phase_uses_default(self) -> None:
        from arc.application.context.protocol import DEFAULT_BUDGET, get_source_budget

        result = get_source_budget("unknown_phase", "domain_model")
        assert result == DEFAULT_BUDGET["domain_model"]

    def test_infer_phase(self) -> None:
        from arc.application.context.prompt_builder import PromptBuilder

        assert PromptBuilder._infer_phase([]) == "clarification"
        assert PromptBuilder._infer_phase(["requirement_spec"]) == "ui_design"
        assert PromptBuilder._infer_phase(
            ["requirement_spec", "interaction_design"]
        ) == "architecture"
        assert PromptBuilder._infer_phase(
            ["requirement_spec", "interaction_design", "tech_architecture"]
        ) == "development"


class TestInferPhaseWithLlm:
    """v6.4 #14: _infer_phase_with_llm 🟡预筛+🟢LLM确认+降级(推进/回退)。"""

    def _make_builder(self):
        from unittest.mock import AsyncMock

        from arc.application.context.prompt_builder import PromptBuilder
        return PromptBuilder(db=AsyncMock())

    async def test_llm_confirms_prefilter(self):
        """LLM 返回预筛一致 → 返回预筛。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            return {"phase": "ui_design"}

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec"], llm_review_fn=llm_fn
        )
        assert phase == "ui_design"

    async def test_llm_advances_phase(self):
        """LLM 推进(预筛 ui_design, LLM 说 architecture) → 返回 architecture。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            return {"phase": "architecture"}

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec"], llm_review_fn=llm_fn
        )
        assert phase == "architecture"

    async def test_llm_regresses_phase(self):
        """LLM 回退(预筛 architecture, LLM 说 ui_design 返工) → 返回 ui_design。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            return {"phase": "ui_design"}

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec", "interaction_design"], llm_review_fn=llm_fn
        )
        assert phase == "ui_design"

    async def test_llm_invalid_phase_falls_back(self):
        """LLM 返回无效 phase → 回退预筛。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            return {"phase": "invalid_phase"}

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec"], llm_review_fn=llm_fn
        )
        assert phase == "ui_design"

    async def test_llm_exception_degrades(self):
        """LLM 异常 → 降级预筛。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            raise RuntimeError("LLM down")

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec"], llm_review_fn=llm_fn
        )
        assert phase == "ui_design"

    async def test_llm_non_dict_falls_back(self):
        """LLM 返回非 dict → 回退预筛。"""
        builder = self._make_builder()

        async def llm_fn(prompt: str) -> dict:
            return "not a dict"  # type: ignore[return-value]

        phase = await builder._infer_phase_with_llm(
            ["requirement_spec"], llm_review_fn=llm_fn
        )
        assert phase == "ui_design"

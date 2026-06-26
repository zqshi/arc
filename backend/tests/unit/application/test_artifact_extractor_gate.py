"""artifact_extractor 门禁接线单元测试。

验证对话模式产出物的"先校验后标记"行为:
- 门禁通过才 mark_produced (PRODUCED)，否则 mark_in_progress (IN_PROGRESS)
- 依赖前置门: strict 硬阻断 / free 软警告 / free 对 deploy_report 仍硬阻断
- _quality 完整写入 artifact.content 并持久化
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.execution.artifact_extractor import ArtifactExtractor
from arc.application.execution.conversation_gate import ConversationGateResult
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.project.value_objects import ProcessConstraint


def _make_extractor() -> ArtifactExtractor:
    """构造 extractor，repo 方法用 AsyncMock 替换。"""
    db = MagicMock()
    ext = ArtifactExtractor(db)
    ext.artifact_repo.update = AsyncMock()
    ext.artifact_repo.list_by_todo_id = AsyncMock(return_value=[])
    return ext


@pytest.fixture
def patch_gate_pass(monkeypatch):
    """让 evaluate_conversation_gate 恒返回通过 (隔离真实 LLM)。"""
    async def fake(artifact_type, content, *, constraint, prior_artifacts=None,
                   conventions="", charter="", capabilities="", llm_review_fn=None):
        return ConversationGateResult(
            passed=True, score=8, threshold=5,
            checked_layers=["structural", "llm_review"],
        )
    monkeypatch.setattr(
        "arc.application.execution.conversation_gate.evaluate_conversation_gate",
        fake,
    )


class TestDependencyGate:
    async def test_strict_blocks_when_prerequisite_missing(self, patch_gate_pass) -> None:
        # strict + tech_architecture，无 requirement_spec 前置 → 硬阻断
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.STRICT, prior_artifacts={},
        )
        assert result is not None
        assert result.passed is False
        assert result.blocked_by_dependency is True
        assert any("requirement_spec" in g for g in result.gaps)

    async def test_strict_passes_when_prerequisite_satisfied(self, patch_gate_pass) -> None:
        # strict + tech_architecture，有 requirement_spec 前置 → 走质量门通过
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.STRICT,
            prior_artifacts={"requirement_spec": {"some": "content"}},
        )
        assert result is not None
        assert result.passed is True
        assert result.blocked_by_dependency is False

    async def test_free_soft_warns_but_does_not_block(self, patch_gate_pass) -> None:
        # free + tech_architecture，无前置 → 软警告不阻断
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.FREE, prior_artifacts={},
        )
        assert result is not None
        assert result.passed is True  # 不阻断
        assert result.dependency_warning == ["requirement_spec"]

    async def test_free_hard_blocks_deploy_report(self, patch_gate_pass) -> None:
        # free 对 deploy_report 仍硬阻断 (没代码没法部署)
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.DEPLOY_REPORT,
            content={"deploy_log": {}, "health_check_result": {}},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.FREE, prior_artifacts={},
        )
        assert result is not None
        assert result.passed is False
        assert result.blocked_by_dependency is True

    async def test_free_hard_blocks_experience_card(self, patch_gate_pass) -> None:
        # free 对 experience_card 硬阻断 (没需求没法提炼经验)
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.EXPERIENCE_CARD,
            content={"problem": "p", "solution": "s", "decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.FREE, prior_artifacts={},
        )
        assert result.passed is False
        assert result.blocked_by_dependency is True


class TestQualityWriteback:
    async def test_quality_written_and_persisted(self, patch_gate_pass) -> None:
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.STRICT,
            prior_artifacts={"requirement_spec": {"x": 1}},
        )
        # _quality 已写入 content
        assert isinstance(artifact.content.get("_quality"), dict)
        assert artifact.content["_quality"]["passed"] is True
        assert artifact.content["_quality"]["score"] == 8
        # 已持久化
        ext.artifact_repo.update.assert_awaited()

    async def test_blocked_result_still_writes_quality(self, patch_gate_pass) -> None:
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}},
        )
        await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.STRICT, prior_artifacts={},
        )
        assert artifact.content["_quality"]["passed"] is False
        assert artifact.content["_quality"]["blocked_by_dependency"] is True

"""artifact_extractor 门禁接线单元测试。

验证对话模式产出物的"先校验后标记"行为:
- 门禁通过才 mark_produced (PRODUCED)，否则 mark_in_progress (IN_PROGRESS)
- 依赖前置门: 三档 (strict/moderate/free) 统一硬阻断 (v6.15 废除 soft 放行)
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
        # strict + tech_architecture，无前置 → 硬阻断 (缺 requirement_spec + prototype)
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
        # strict + tech_architecture，前置全达标 (requirement_spec + prototype) → 走质量门通过
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.STRICT,
            prior_artifacts={
                "requirement_spec": {"some": "content"},
                "prototype": {"project_dir": "/x", "routes": [], "build_status": "ok"},
            },
        )
        assert result is not None
        assert result.passed is True
        assert result.blocked_by_dependency is False

    async def test_free_hard_blocks_when_prerequisite_missing(self, patch_gate_pass) -> None:
        # v6.15: free 也硬阻断 (废除 soft 放行) — 缺前置不再"软警告放行"
        # 堵"没需求/没原型就开始后续环节"的空中楼阁, 依赖约束与档位无关
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
        assert result.passed is False  # v6.15: free 不再放行
        assert result.blocked_by_dependency is True

    async def test_moderate_hard_blocks_when_prerequisite_missing(self, patch_gate_pass) -> None:
        # 三档统一硬阻断的第三档验证 (moderate)
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}, "api_design": [], "tech_decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.MODERATE, prior_artifacts={},
        )
        assert result is not None
        assert result.passed is False
        assert result.blocked_by_dependency is True

    async def test_free_hard_blocks_deploy_report(self, patch_gate_pass) -> None:
        # free + deploy_report 无前置 (dev_report/app_code/test_report) → 硬阻断
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
        # free + experience_card 无前置 (requirement_spec + dev_report) → 硬阻断
        ext = _make_extractor()
        artifact = Artifact(
            todo_id=MagicMock(), artifact_type=ArtifactType.EXPERIENCE_CARD,
            content={"problem": "p", "solution": "s", "decisions": []},
        )
        result = await ext._validate_extracted_artifact(
            artifact, MagicMock(),
            constraint=ProcessConstraint.FREE, prior_artifacts={},
        )
        assert result is not None
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
            prior_artifacts={
                "requirement_spec": {"x": 1},
                "prototype": {"project_dir": "/x", "routes": [], "build_status": "ok"},
            },
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

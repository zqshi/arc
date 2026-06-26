"""对话模式质量门禁单元测试。"""

from __future__ import annotations

from arc.application.execution.conversation_gate import (
    check_deliverable_fields,
    evaluate_conversation_gate,
)
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.project.value_objects import ProcessConstraint


def _complete_req_spec() -> dict:
    return {
        "background": "解决某问题",
        "user_stories": [{"id": "US1", "role": "用户", "priority": "P0"}],
        "acceptance_criteria": [{"id": "AC1"}],
        "boundaries": {"in_scope": ["a"], "out_of_scope": ["b"]},
    }


def _llm_reviewer(score: int, gaps=None):
    """构造注入用 LLM 评审函数。"""
    async def fn(prompt: str) -> dict:
        return {"passed": score >= 5, "score": score, "gaps": gaps or [], "suggestion": "ok"}

    return fn


class TestCheckDeliverableFields:
    def test_complete_content_no_gaps(self) -> None:
        gaps = check_deliverable_fields(ArtifactType.REQUIREMENT_SPEC, _complete_req_spec())
        assert gaps == []

    def test_missing_field_reported(self) -> None:
        content = _complete_req_spec()
        del content["user_stories"]
        gaps = check_deliverable_fields(ArtifactType.REQUIREMENT_SPEC, content)
        assert any("user_stories" in g for g in gaps)

    def test_placeholder_string_reported(self) -> None:
        content = _complete_req_spec()
        content["background"] = "待补充"
        gaps = check_deliverable_fields(ArtifactType.REQUIREMENT_SPEC, content)
        assert any("background" in g for g in gaps)

    def test_empty_list_reported(self) -> None:
        content = _complete_req_spec()
        content["user_stories"] = []
        gaps = check_deliverable_fields(ArtifactType.REQUIREMENT_SPEC, content)
        assert any("user_stories" in g for g in gaps)

    def test_unknown_type_no_gaps(self) -> None:
        assert check_deliverable_fields(ArtifactType.UI_DESIGN, {}) == []


class TestEvaluateConversationGate:
    async def test_free_passes_at_score_above_threshold(self) -> None:
        # free 阈值 5，LLM 给 6 → 通过
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(6),
        )
        assert result.passed is True
        assert result.threshold == 5
        assert "llm_review" in result.checked_layers

    async def test_free_fails_below_threshold(self) -> None:
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(4),
        )
        assert result.passed is False  # 4 < 5

    async def test_strict_threshold_is_7(self) -> None:
        # strict 阈值 7，6 分不通过
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.STRICT, llm_review_fn=_llm_reviewer(6),
        )
        assert result.passed is False
        assert result.threshold == 7

    async def test_moderate_threshold_is_6(self) -> None:
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.MODERATE, llm_review_fn=_llm_reviewer(6),
        )
        assert result.passed is True

    async def test_structural_short_circuit_skips_llm(self) -> None:
        # app_code 有 5 个必填字段，全空 → 5 缺口 ≥ free short_circuit(5) → 短路不调 LLM
        called = []

        async def fn(prompt: str) -> dict:
            called.append(prompt)
            return {"score": 10}

        result = await evaluate_conversation_gate(
            ArtifactType.APP_CODE, {},
            constraint=ProcessConstraint.FREE, llm_review_fn=fn,
        )
        assert result.passed is False
        assert result.score == 2
        assert called == []  # LLM 未被调用
        assert "llm_review" not in result.checked_layers

    async def test_free_does_not_run_methodology(self) -> None:
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(8),
        )
        assert "methodology" not in result.checked_layers

    async def test_unknown_artifact_passes(self) -> None:
        result = await evaluate_conversation_gate(
            ArtifactType.UI_DESIGN, {},
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(8),
        )
        assert result.passed is True

    async def test_to_quality_format(self) -> None:
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(8),
        )
        quality = result.to_quality()
        assert set(quality.keys()) == {
            "passed", "score", "gaps", "suggestion", "threshold",
            "blocked_by_dependency", "dependency_warning", "checked_layers",
        }
        assert quality["passed"] is True
        assert quality["threshold"] == 5

    async def test_structural_gap_blocks_even_if_llm_high(self) -> None:
        # 有结构缺口但未达短路阈值 → 跑 LLM，但结构缺口非零 → 不通过
        content = _complete_req_spec()
        del content["boundaries"]  # 1 个缺口 < short_circuit(5)
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, content,
            constraint=ProcessConstraint.FREE, llm_review_fn=_llm_reviewer(10),
        )
        assert result.passed is False  # 结构缺口存在
        assert any("boundaries" in g for g in result.gaps)


class TestCharterCompliance:
    """charter 遵守度门禁 — charter 注入 LLM 评审 prompt (波次3)。"""

    @staticmethod
    def _capturing_reviewer(captured: list[str], score: int = 8, gaps=None):
        """捕获 prompt + 返回固定评审结果。"""
        async def fn(prompt: str) -> dict:
            captured.append(prompt)
            return {"passed": score >= 5, "score": score, "gaps": gaps or [], "suggestion": "ok"}
        return fn

    async def test_charter_injected_into_llm_prompt(self) -> None:
        """传 charter → LLM 评审 prompt 含 charter 内容 + section 标记。"""
        captured: list[str] = []
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.STRICT,
            charter="## 静态站点特化治理意图\n### 可发现性意图 (SEO)\n- 目标: 页面有准确标题",
            llm_review_fn=self._capturing_reviewer(captured),
        )
        assert result.passed is True
        assert len(captured) == 1
        assert "可发现性意图" in captured[0]
        assert "项目宪章" in captured[0]

    async def test_empty_charter_omits_section(self) -> None:
        """空 charter → prompt 不含 charter_section (不污染)。"""
        captured: list[str] = []
        await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.STRICT,
            charter="",
            llm_review_fn=self._capturing_reviewer(captured),
        )
        assert "项目宪章" not in captured[0]

    async def test_charter_violation_lowers_score_and_blocks(self) -> None:
        """charter 违规 (LLM 返回低分 + charter 相关 gap) → passed=False。"""
        result = await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.STRICT,
            charter="### 离线降级意图 (PWA)\n- 目标: 离线不白屏",
            llm_review_fn=_llm_reviewer(3, gaps=["未实现离线降级,违反 PWA 治理意图"]),
        )
        assert result.passed is False
        assert result.score == 3
        assert any("PWA" in g or "离线" in g for g in result.gaps)

    async def test_conventions_also_injected_alongside_charter(self) -> None:
        """conventions + charter 同时注入 (两者并列, 顺带验证 conventions 接通)。"""
        captured: list[str] = []
        await evaluate_conversation_gate(
            ArtifactType.REQUIREMENT_SPEC, _complete_req_spec(),
            constraint=ProcessConstraint.STRICT,
            conventions="用户手填规范: 必须有错误处理",
            charter="## 项目宪章治理意图\n- 安全意图",
            llm_review_fn=self._capturing_reviewer(captured),
        )
        assert "用户手填规范" in captured[0]
        assert "项目宪章" in captured[0]

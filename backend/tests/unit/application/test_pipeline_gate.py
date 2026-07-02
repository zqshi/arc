"""pipeline/gate.py evaluate_gate 直接单测。

填补历史空白: test_pipeline_service.py 整体 mock 掉 evaluate_gate,
导致 evaluate_gate 函数体 (含死循环根因 gate.py:149) 长期零直接覆盖。
本文件按 TDD 先写复现测试, 再驱动 P0/P1 修复。

覆盖矩阵:
- passed 完全由 score >= threshold 推导, 不读 LLM 返回的 passed 字段 (P0 死循环根因)
- 结构缺口阻断, 不受 score 影响
- 解析失败返回 score=0 哨兵 (供 P2 故障逃生阀识别)
- p0_gaps 阻断, gaps 不阻断 (P1 rubric 契约)
- gaps 去重保序 (set()→dict.fromkeys())
"""

from __future__ import annotations

from arc.application.pipeline.gate import evaluate_gate
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.project.value_objects import ProcessConstraint


def _complete_clarification() -> dict:
    """完整 clarification 产出物 — 结构校验零缺口, 方法论跳过 (无 user_stories)。

    使 evaluate_gate 跑到 LLM 层, passed 完全由 score 决定。
    """
    return {
        "background": "解决某问题",
        "target_users": [{"type": "用户"}],
        "user_scenarios": ["场景1"],
        "boundaries": {"in_scope": ["a"], "out_of_scope": ["b"]},
        "acceptance_criteria": [{"id": "AC1"}],
    }


def _reviewer(*, score: int, passed: bool = True, gaps=None, p0_gaps=None):
    """构造注入用 LLM 评审函数 (签名 (prompt)->dict, 与 conversation_gate 统一)。

    passed 与 score 解耦 — 用于复现"LLM 说 passed=false 但 score 高"的死循环。
    """
    async def fn(prompt: str) -> dict:
        data: dict = {"score": score, "gaps": gaps or [], "suggestion": "ok"}
        # passed 字段保留以验证"代码不再读它"(P0), P1 后 prompt 不再要求该字段
        data["passed"] = passed
        if p0_gaps is not None:
            data["p0_gaps"] = p0_gaps
        return data

    return fn


class TestEvaluateGateScoreDriven:
    """P0: passed 由 score >= threshold 推导, 不读 LLM passed 字段。"""

    async def test_passed_is_score_driven_not_llm_passed(self) -> None:
        """死循环复现: LLM 返回 passed=False 但 score=9 (>=strict 阈值 7) → 应通过。

        修复前 gate.py:149 吃 LLM passed 字段 → passed=False → strict 永久卡死。
        """
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=_reviewer(score=9, passed=False),
        )
        assert result.passed is True
        assert result.score == 9

    async def test_low_score_fails_regardless_llm_passed(self) -> None:
        """LLM 返回 passed=True 但 score=6 (<strict 阈值 7) → 不通过 (score 守门)。"""
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=_reviewer(score=6, passed=True),
        )
        assert result.passed is False

    async def test_free_threshold_is_5(self) -> None:
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.FREE,
            llm_review_fn=_reviewer(score=5, passed=False),
        )
        assert result.passed is True  # 5 >= 5

    async def test_moderate_threshold_is_6(self) -> None:
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.MODERATE,
            llm_review_fn=_reviewer(score=6, passed=False),
        )
        assert result.passed is True


class TestEvaluateGateStructural:
    """结构缺口阻断, 不受 score 影响。"""

    async def test_structural_gap_fails_regardless_of_score(self) -> None:
        """结构有 1 缺口 (<短路阈值) + score=10 → 仍不通过。"""
        content = _complete_clarification()
        del content["background"]
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, content,
            constraint=ProcessConstraint.FREE,
            llm_review_fn=_reviewer(score=10, passed=True),
        )
        assert result.passed is False
        assert any("background" in g for g in result.gaps)

    async def test_structural_short_circuit_skips_llm(self) -> None:
        """结构缺口 >= short_circuit 直接失败不调 LLM (省成本)。"""
        called = []

        async def fn(prompt: str) -> dict:
            called.append(prompt)
            return {"score": 10}

        # UI_DESIGN 必填 3 字段, 全空 → 3 缺口 >= free short_circuit(5)? 否, 3<5
        # 用 DEVELOPMENT: 必填 3 字段全空, strict short_circuit=3 → 3>=3 短路
        result = await evaluate_gate(
            PhaseType.DEVELOPMENT, {},
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=fn,
        )
        assert result.passed is False
        assert result.score == 2  # 短路固定低分
        assert called == []


class TestEvaluateGateParseFailure:
    """P0: 解析失败返回 score=0 哨兵 (供 P2 故障逃生阀识别)。"""

    async def test_parse_failure_returns_score_zero_sentinel(self) -> None:
        """LLM 返回非 dict (解析失败) → score=0 (非 4), 文案明示基础设施故障。"""
        async def fn(prompt: str):
            return "not a dict"  # 解析失败

        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=fn,
        )
        assert result.passed is False
        assert result.score == 0  # 哨兵值, 区分"未评审" vs "评了但差"

    async def test_parse_failure_suggestion_mentions_infra(self) -> None:
        async def fn(prompt: str):
            return None

        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=fn,
        )
        # 文案应暗示"评审基础设施故障"而非"产出物不合格"
        assert "评审" in result.suggestion or "技术" in result.suggestion


class TestEvaluateGateGapsDedup:
    """gaps 去重保序 (set()→dict.fromkeys())。"""

    async def test_gaps_dedup_preserves_order(self) -> None:
        """结构 gap 与 LLM gap 重复时去重, 且保持 [结构, LLM 其他] 顺序。"""
        content = _complete_clarification()
        del content["background"]  # 结构 gap: "缺少必填字段「background」"
        structural_gap_prefix = "缺少必填字段「background」"

        result = await evaluate_gate(
            PhaseType.CLARIFICATION, content,
            constraint=ProcessConstraint.FREE,
            llm_review_fn=_reviewer(
                score=10, gaps=[structural_gap_prefix, "另外的建议"],
            ),
        )
        # 去重: structural_gap 只出现一次; 保序: 结构在前, LLM 其他在后
        assert result.gaps.count(structural_gap_prefix) == 1
        assert result.gaps[0].startswith("缺少必填字段")
        assert "另外的建议" in result.gaps


class TestEvaluateGateP0Gaps:
    """P1: LLM p0_gaps (阻断性缺口) 致 fail, gaps (改进建议) 不阻断。"""

    async def test_p0_gap_blocks_pass(self) -> None:
        """LLM 返回 score=9 (>=strict 阈值) 但有 p0_gap → 不通过。"""
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=_reviewer(score=9, p0_gaps=["致命缺口: 自相矛盾"]),
        )
        assert result.passed is False
        assert any("致命缺口" in g for g in result.gaps)

    async def test_improvement_gap_does_not_block(self) -> None:
        """LLM 返回 score=9 + 仅 gaps (改进建议, 无 p0) → 通过。"""
        result = await evaluate_gate(
            PhaseType.CLARIFICATION, _complete_clarification(),
            constraint=ProcessConstraint.STRICT,
            llm_review_fn=_reviewer(score=9, gaps=["建议补充更多细节"]),
        )
        assert result.passed is True
        assert any("更多细节" in g for g in result.gaps)

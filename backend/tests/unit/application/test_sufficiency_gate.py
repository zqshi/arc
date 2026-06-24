"""sufficiency 产出门禁单元测试 — v6.0 #7。

被测: evaluate_sufficiency — 产出 requirement_spec 前判断对话信息是否足够。
LLM 三维评估(target_users/core_problem/feature_direction), 降级放行(不阻断)。
"""

from __future__ import annotations

import pytest

from arc.application.execution.sufficiency_gate import (
    SufficiencyResult,
    evaluate_sufficiency,
)


def _llm_returning(payload: dict):
    """构造注入用 llm_review_fn, 返回固定 payload。"""
    async def _fn(prompt: str) -> dict:
        return payload
    return _fn


def _llm_raising(exc: Exception):
    """构造注入用 llm_review_fn, 抛异常(模拟 LLM 不可用)。"""
    async def _fn(prompt: str) -> dict:
        raise exc
    return _fn


class TestSufficiencyGate:
    """evaluate_sufficiency 行为族。"""

    async def test_sufficient_when_all_dimensions_clear(self) -> None:
        result = await evaluate_sufficiency(
            title="官网重构", description="...",
            conversation_summary="用户明确目标用户是设计师...",
            llm_review_fn=_llm_returning({
                "sufficient": True,
                "target_users": {"status": "clear", "evidence": "设计师"},
                "core_problem": {"status": "clear", "evidence": "加载慢"},
                "feature_direction": {"status": "clear", "evidence": "PWA"},
                "follow_up_questions": [],
            }),
        )
        assert result.sufficient is True
        assert result.follow_up_questions == []
        assert result.target_users.status == "clear"

    async def test_insufficient_when_dimension_missing(self) -> None:
        result = await evaluate_sufficiency(
            title="某项目", description="",
            conversation_summary="用户只说了想做官网",
            llm_review_fn=_llm_returning({
                "sufficient": False,
                "target_users": {"status": "vague", "evidence": ""},
                "core_problem": {"status": "missing", "evidence": ""},
                "feature_direction": {"status": "missing", "evidence": ""},
                "follow_up_questions": ["目标用户是谁?", "要解决什么问题?"],
            }),
        )
        assert result.sufficient is False
        assert len(result.follow_up_questions) == 2
        assert result.core_problem.status == "missing"

    async def test_llm_failure_degrades_to_sufficient(self) -> None:
        """LLM 不可用时降级放行, 不阻断主流程。"""
        result = await evaluate_sufficiency(
            title="x", description="y", conversation_summary="z",
            llm_review_fn=_llm_raising(RuntimeError("LLM down")),
        )
        assert result.sufficient is True
        assert result.follow_up_questions == []

    async def test_malformed_llm_output_degrades_to_sufficient(self) -> None:
        """LLM 返回非 dict / 缺 sufficient 字段时降级放行。"""
        result = await evaluate_sufficiency(
            title="x", description="y", conversation_summary="z",
            llm_review_fn=_llm_returning({"unrelated": "field"}),  # 缺 sufficient
        )
        assert result.sufficient is True

    async def test_dimension_status_parsed(self) -> None:
        """三维 status 从 LLM 输出正确解析。"""
        result = await evaluate_sufficiency(
            title="x", description="y", conversation_summary="z",
            llm_review_fn=_llm_returning({
                "sufficient": False,
                "target_users": {"status": "vague", "evidence": "提到设计师但不确定"},
                "core_problem": {"status": "clear", "evidence": "加载慢"},
                "feature_direction": {"status": "missing", "evidence": ""},
                "follow_up_questions": ["功能方向?"],
            }),
        )
        assert result.target_users.status == "vague"
        assert result.core_problem.status == "clear"
        assert result.feature_direction.status == "missing"

    async def test_default_reviewer_path_not_crash(self) -> None:
        """不注入 llm_review_fn 时走默认 resilient adapter 路径不崩溃。

        默认 adapter 调真实/mock LLM, sufficient 值取决于 LLM 判断不可控,
        故只验证不抛异常 + 返回 SufficiencyResult。
        """
        result = await evaluate_sufficiency(
            title="x", description="y", conversation_summary="z",
        )
        assert isinstance(result, SufficiencyResult)

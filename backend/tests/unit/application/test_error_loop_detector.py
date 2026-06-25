"""Unit tests for ErrorLoopDetector — v6.3 #9 (LLM 化)。

LCS 降级路径 (llm_review_fn=None) 保留现状行为 + LLM 语义确认路径。
"""

from __future__ import annotations

from arc.application.execution.error_loop_detector import (
    ErrorLoopDetector,
    ErrorLoopJudgement,
)


def _llm_returning(payload):
    async def _fn(prompt: str):
        return payload
    return _fn


def _llm_raising(exc: Exception):
    async def _fn(prompt: str):
        raise exc
    return _fn


class TestErrorLoopDetection:
    """LCS 降级路径 (llm_review_fn=None, 现状行为保留)。"""

    async def test_no_loop_short_history(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        assert await detector.record_and_check("action_1") is False
        assert await detector.record_and_check("action_2") is False
        assert await detector.record_and_check("action_3") is False

    async def test_period_2_loop(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        # A B A B A B → period 2
        await detector.record_and_check("read_file:/error.py")
        await detector.record_and_check("run_command:npm test")
        await detector.record_and_check("read_file:/error.py")
        await detector.record_and_check("run_command:npm test")
        await detector.record_and_check("read_file:/error.py")
        result = await detector.record_and_check("run_command:npm test")
        assert result is True

    async def test_period_3_loop(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        # A B C A B C → period 3
        await detector.record_and_check("step_a")
        await detector.record_and_check("step_b")
        await detector.record_and_check("step_c")
        await detector.record_and_check("step_a")
        await detector.record_and_check("step_b")
        result = await detector.record_and_check("step_c")
        assert result is True

    async def test_no_loop_varied_actions(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        actions = ["read_file:main.py", "grep:pattern", "write_file:out.py",
                    "run_command:test", "list_dir:src", "read_file:config.py",
                    "grep:error", "run_command:build", "write_file:new.py",
                    "list_dir:docs"]
        result = False
        for a in actions:
            result = await detector.record_and_check(a)
        assert result is False

    async def test_similar_but_not_identical(self) -> None:
        """Actions that are similar but not 85% similar should not trigger."""
        detector = ErrorLoopDetector(window_size=6, similarity_threshold=0.85)
        actions = [
            "read_file:src/auth/login.ts",
            "grep_search:password",
            "read_file:src/api/client.ts",
            "run_command:npm test",
            "write_file:src/utils/helper.ts",
            "read_file:docs/README.md",
        ]
        result = False
        for a in actions:
            result = await detector.record_and_check(a)
        assert result is False


class TestErrorLoopCount:
    async def test_loop_count_increments(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        assert detector.loop_count == 0
        # Create a period-2 loop
        for _ in range(3):
            await detector.record_and_check("A")
            await detector.record_and_check("B")
        # First detection at index 5 (6th call)
        assert detector.loop_count >= 1

    async def test_reset_clears_count(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        for _ in range(3):
            await detector.record_and_check("X")
            await detector.record_and_check("Y")
        detector.reset()
        assert detector.loop_count == 0


class TestErrorLoopBreakPrompt:
    def test_first_detection_mild(self) -> None:
        detector = ErrorLoopDetector()
        detector._loop_count = 1
        prompt = detector.get_break_prompt()
        assert "注意" in prompt
        assert "换一种方法" in prompt

    def test_repeated_detection_urgent(self) -> None:
        detector = ErrorLoopDetector()
        detector._loop_count = 2
        prompt = detector.get_break_prompt()
        assert "紧急" in prompt
        assert "完全不同" in prompt


class TestSimilarity:
    def test_identical(self) -> None:
        assert ErrorLoopDetector._similarity("hello", "hello") == 1.0

    def test_empty(self) -> None:
        assert ErrorLoopDetector._similarity("", "hello") == 0.0

    def test_partial_overlap(self) -> None:
        sim = ErrorLoopDetector._similarity("abcdef", "abcxyz")
        assert 0.3 < sim < 0.8

    def test_completely_different(self) -> None:
        sim = ErrorLoopDetector._similarity("abc", "xyz")
        assert sim < 0.3


# ----------------------------------------------------------------------
# v6.3 #9: LLM 语义判断
# ----------------------------------------------------------------------


class TestErrorLoopJudgement:
    """ErrorLoopJudgement.from_llm 解析 + 降级信号。"""

    def test_valid_llm_output(self) -> None:
        j = ErrorLoopJudgement.from_llm(
            {"is_same_error_loop": True, "confidence": 0.8, "reason": "权限循环"}
        )
        assert j is not None
        assert j.is_same_error_loop is True
        assert j.confidence == 0.8
        assert j.reason == "权限循环"

    def test_missing_is_same_error_loop_returns_none(self) -> None:
        assert ErrorLoopJudgement.from_llm({"confidence": 0.5}) is None

    def test_non_dict_returns_none(self) -> None:
        assert ErrorLoopJudgement.from_llm("not dict") is None
        assert ErrorLoopJudgement.from_llm(None) is None

    def test_confidence_clamped(self) -> None:
        j = ErrorLoopJudgement.from_llm({"is_same_error_loop": False, "confidence": 1.5})
        assert j is not None and j.confidence == 1.0
        j = ErrorLoopJudgement.from_llm({"is_same_error_loop": False, "confidence": -0.3})
        assert j is not None and j.confidence == 0.0

    def test_invalid_confidence_defaults_half(self) -> None:
        j = ErrorLoopJudgement.from_llm({"is_same_error_loop": True, "confidence": "high"})
        assert j is not None and j.confidence == 0.5


class TestErrorLoopLLM:
    """LLM 语义确认路径 (窗口满 + 有错误 + LCS 判否时触发)。"""

    async def test_lcs_loop_skips_llm(self) -> None:
        """LCS 结构预筛判 True 时不调 LLM。"""
        called: list[str] = []

        async def llm_fn(prompt: str):
            called.append(prompt)
            return {"is_same_error_loop": False, "confidence": 0.99}

        detector = ErrorLoopDetector(window_size=6, llm_review_fn=llm_fn)
        # period-2 重复 (带错误, 但 LCS 优先)
        for _ in range(3):
            await detector.record_and_check("read_file:x.py", error_summary="err")
            await detector.record_and_check("run_command:y", error_summary="err")
        assert detector.loop_count >= 1
        assert called == []  # LLM 未调用

    async def test_llm_confirms_same_error_loop(self) -> None:
        """窗口满 + 有错误 + LCS 判否 → LLM 判同类错 → True。"""
        detector = ErrorLoopDetector(
            window_size=6,
            llm_review_fn=_llm_returning(
                {"is_same_error_loop": True, "confidence": 0.8, "reason": "权限循环"}
            ),
        )
        # 6 个不同签名 (LCS 判否), 前2个带错误
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is True
        assert detector.loop_count == 1

    async def test_llm_says_not_loop(self) -> None:
        """LLM 判非同类错 → False。"""
        detector = ErrorLoopDetector(
            window_size=6,
            llm_review_fn=_llm_returning({"is_same_error_loop": False, "confidence": 0.9}),
        )
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False
        assert detector.loop_count == 0

    async def test_llm_low_confidence_not_triggered(self) -> None:
        """LLM 判同类错但置信度 <0.6 → 不触发。"""
        detector = ErrorLoopDetector(
            window_size=6,
            llm_review_fn=_llm_returning({"is_same_error_loop": True, "confidence": 0.4}),
        )
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False

    async def test_llm_exception_degrades_to_false(self) -> None:
        """LLM 异常 → 降级 False (LCS 已判否)。"""
        detector = ErrorLoopDetector(
            window_size=6,
            llm_review_fn=_llm_raising(RuntimeError("LLM down")),
        )
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False

    async def test_llm_malformed_output_degrades(self) -> None:
        """LLM 返回非 dict → 降级 False。"""
        detector = ErrorLoopDetector(
            window_size=6,
            llm_review_fn=_llm_returning("not json"),
        )
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False

    async def test_no_error_summary_skips_llm(self) -> None:
        """无错误 → 不调 LLM (控成本)。"""
        called: list[str] = []

        async def llm_fn(prompt: str):
            called.append(prompt)
            return {"is_same_error_loop": True, "confidence": 0.99}

        detector = ErrorLoopDetector(window_size=6, llm_review_fn=llm_fn)
        # 6 个不同签名, 无错误
        await detector.record_and_check("read_file:a.py")
        await detector.record_and_check("cat:a.py")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False
        assert called == []  # 无错误, LLM 未调用

    async def test_no_llm_fn_degrades_to_lcs(self) -> None:
        """未注入 llm_review_fn → 降级 LCS。"""
        detector = ErrorLoopDetector(window_size=6)
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        result = await detector.record_and_check("find:a.py")
        assert result is False  # LCS 判否, 无 LLM

    async def test_llm_prompt_carries_signatures_and_errors(self) -> None:
        """LLM prompt 应包含签名和错误摘要。"""
        captured: list[str] = []

        async def llm_fn(prompt: str):
            captured.append(prompt)
            return {"is_same_error_loop": True, "confidence": 0.9}

        detector = ErrorLoopDetector(window_size=6, llm_review_fn=llm_fn)
        await detector.record_and_check("read_file:a.py", error_summary="permission denied")
        await detector.record_and_check("cat:a.py", error_summary="permission denied")
        await detector.record_and_check("sed:a.py")
        await detector.record_and_check("grep:a.py")
        await detector.record_and_check("ls:a.py")
        await detector.record_and_check("find:a.py")
        assert len(captured) == 1
        assert "read_file:a.py" in captured[0]
        assert "permission denied" in captured[0]

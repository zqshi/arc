"""Unit tests for ErrorLoopDetector."""

from __future__ import annotations

from arc.application.execution.error_loop_detector import ErrorLoopDetector


class TestErrorLoopDetection:
    def test_no_loop_short_history(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        assert detector.record_and_check("action_1") is False
        assert detector.record_and_check("action_2") is False
        assert detector.record_and_check("action_3") is False

    def test_period_2_loop(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        # A B A B A B → period 2
        detector.record_and_check("read_file:/error.py")
        detector.record_and_check("run_command:npm test")
        detector.record_and_check("read_file:/error.py")
        detector.record_and_check("run_command:npm test")
        detector.record_and_check("read_file:/error.py")
        result = detector.record_and_check("run_command:npm test")
        assert result is True

    def test_period_3_loop(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        # A B C A B C → period 3
        detector.record_and_check("step_a")
        detector.record_and_check("step_b")
        detector.record_and_check("step_c")
        detector.record_and_check("step_a")
        detector.record_and_check("step_b")
        result = detector.record_and_check("step_c")
        assert result is True

    def test_no_loop_varied_actions(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        # Use truly different strings (not just suffix changes)
        actions = ["read_file:main.py", "grep:pattern", "write_file:out.py",
                    "run_command:test", "list_dir:src", "read_file:config.py",
                    "grep:error", "run_command:build", "write_file:new.py",
                    "list_dir:docs"]
        result = False
        for a in actions:
            result = detector.record_and_check(a)
        assert result is False

    def test_similar_but_not_identical(self) -> None:
        """Actions that are similar but not 85% similar should not trigger."""
        detector = ErrorLoopDetector(window_size=6, similarity_threshold=0.85)
        # Truly different file paths in different directories
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
            result = detector.record_and_check(a)
        assert result is False


class TestErrorLoopCount:
    def test_loop_count_increments(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        assert detector.loop_count == 0
        # Create a period-2 loop
        for _ in range(3):
            detector.record_and_check("A")
            detector.record_and_check("B")
        # First detection at index 5 (6th call)
        assert detector.loop_count >= 1

    def test_reset_clears_count(self) -> None:
        detector = ErrorLoopDetector(window_size=6)
        for _ in range(3):
            detector.record_and_check("X")
            detector.record_and_check("Y")
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

"""Unit tests for DriftDetector."""

from __future__ import annotations

from arc.application.execution.drift_detector import (
    DriftDetector,
    DriftLevel,
    _extract_keywords,
    _string_similarity,
)


class TestExtractKeywords:
    def test_english_keywords(self) -> None:
        kw = _extract_keywords("Fix the login bug in auth module")
        assert "fix" in kw
        assert "login" in kw
        assert "auth" in kw
        # Single-char words filtered
        assert "a" not in kw

    def test_chinese_keywords(self) -> None:
        kw = _extract_keywords("修复用户登录模块的错误")
        # 中文没有空格分词，整个连续串作为一个 token
        # 只有被标点/空格分隔的部分才是独立 token
        assert len(kw) >= 1
        # Stopwords in Chinese are single chars, they won't match multi-char tokens
        # The whole string without stopwords is kept
        assert any("修复" in k for k in kw)

    def test_empty_string(self) -> None:
        assert _extract_keywords("") == set()

    def test_numbers_filtered(self) -> None:
        kw = _extract_keywords("version 123 release")
        assert "123" not in kw


class TestStringSimilarity:
    def test_identical_strings(self) -> None:
        assert _string_similarity("hello", "hello") == 1.0

    def test_empty_strings(self) -> None:
        assert _string_similarity("", "") == 0.0
        assert _string_similarity("hello", "") == 0.0

    def test_similar_strings(self) -> None:
        sim = _string_similarity("read_file:/src/main.py", "read_file:/src/main.py")
        assert sim == 1.0

    def test_different_strings(self) -> None:
        sim = _string_similarity("abc", "xyz")
        assert sim < 0.5


class TestDriftDetectorLevels:
    def test_relevant_action_no_drift(self) -> None:
        detector = DriftDetector("fix login page bug")
        level = detector.check_drift("reading login page code to fix bug")
        assert level == DriftLevel.NONE

    def test_irrelevant_action_severe(self) -> None:
        detector = DriftDetector("fix login page bug")
        level = detector.check_drift("restructure database schema for analytics pipeline")
        assert level >= DriftLevel.MODERATE

    def test_no_goal_keywords_defaults_neutral(self) -> None:
        detector = DriftDetector("")  # empty goal
        level = detector.check_drift("some random action")
        # Empty goal → relevance returns 0.5 → NONE
        assert level == DriftLevel.NONE


class TestDriftDetectorLoop:
    def test_repetition_loop_detected(self) -> None:
        detector = DriftDetector("fix bug", similarity_window=4)
        # Period-2 repetition: A B A B
        detector.check_drift("action_a")
        detector.check_drift("action_b")
        detector.check_drift("action_a")
        result = detector.check_drift("action_b")
        assert result == DriftLevel.SEVERE

    def test_no_loop_in_varied_actions(self) -> None:
        """Varied actions should not trigger loop detection (SEVERE via _detect_loop)."""
        detector = DriftDetector("read files and grep code", similarity_window=6)
        actions = ["read main.py", "grep error pattern", "read config.py",
                   "grep import statement", "read utils.py", "grep function def"]
        level = DriftLevel.NONE
        for a in actions:
            level = detector.check_drift(a)
        # May drift on relevance, but should NOT be SEVERE from loop detection
        # since all actions are distinct
        assert level != DriftLevel.SEVERE or not detector._detect_loop()


class TestDriftDetectorRefocusPrompt:
    def test_mild_prompt(self) -> None:
        detector = DriftDetector("目标任务")
        prompt = detector.get_refocus_prompt(DriftLevel.MILD)
        assert "提醒" in prompt
        assert "目标任务" in prompt

    def test_moderate_prompt(self) -> None:
        detector = DriftDetector("目标任务")
        prompt = detector.get_refocus_prompt(DriftLevel.MODERATE)
        assert "重新聚焦" in prompt

    def test_severe_prompt(self) -> None:
        detector = DriftDetector("目标任务")
        prompt = detector.get_refocus_prompt(DriftLevel.SEVERE)
        assert "紧急" in prompt

    def test_none_returns_empty(self) -> None:
        detector = DriftDetector("goal")
        assert detector.get_refocus_prompt(DriftLevel.NONE) == ""


class TestDriftDetectorReset:
    def test_reset_clears_history(self) -> None:
        detector = DriftDetector("goal")
        detector.check_drift("a")
        detector.check_drift("b")
        detector.reset()
        # After reset, no loop should be detected immediately
        level = detector.check_drift("a")
        assert level != DriftLevel.SEVERE

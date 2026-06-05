"""DriftDetector 单元测试。"""

from __future__ import annotations

from arc.application.execution.drift_detector import (
    DriftDetector,
    DriftLevel,
    _extract_keywords,
    _string_similarity,
)


class TestDriftDetectorCreation:
    def test_initial_state(self) -> None:
        detector = DriftDetector("实现用户登录功能")
        assert detector._original_goal == "实现用户登录功能"
        assert detector._action_history == []

    def test_goal_keywords_extracted(self) -> None:
        detector = DriftDetector("implement user login feature")
        assert "implement" in detector._goal_keywords
        assert "user" in detector._goal_keywords


class TestCheckDrift:
    def test_relevant_action_returns_low_drift(self) -> None:
        detector = DriftDetector("implement user login feature with password validation")
        level = detector.check_drift("implementing the user login password validation logic")
        # 高度相关的行为应不超过 MILD
        assert level <= DriftLevel.MILD

    def test_irrelevant_action_returns_high_drift(self) -> None:
        detector = DriftDetector("implement user login feature")
        level = detector.check_drift("configuring kubernetes cluster network policy and service mesh deployment")
        # 与目标完全无关，应当为 MODERATE 或 SEVERE
        assert level >= DriftLevel.MODERATE

    def test_partially_relevant_action(self) -> None:
        detector = DriftDetector("develop order payment module supporting wechat and alipay")
        level = detector.check_drift("checking alipay sdk version compatibility for payment")
        # 部分相关
        assert level <= DriftLevel.MODERATE

    def test_repetition_loop_triggers_severe(self) -> None:
        detector = DriftDetector("complete data export feature", similarity_window=4)
        # 人为构造重复模式
        for _ in range(3):
            detector.check_drift("read_file:export.py")
            detector.check_drift("run_command:npm test")

        # 重复模式应被检测为 SEVERE
        level = detector.check_drift("read_file:export.py")
        assert level == DriftLevel.SEVERE

    def test_reset_clears_history(self) -> None:
        detector = DriftDetector("test goal")
        detector.check_drift("action 1")
        detector.check_drift("action 2")
        detector.reset()
        assert detector._action_history == []


class TestGetRefocusPrompt:
    def test_none_level_returns_empty(self) -> None:
        detector = DriftDetector("目标")
        prompt = detector.get_refocus_prompt(DriftLevel.NONE)
        assert prompt == ""

    def test_mild_level_includes_reminder(self) -> None:
        detector = DriftDetector("complete data export feature")
        prompt = detector.get_refocus_prompt(DriftLevel.MILD)
        assert "提醒" in prompt
        assert "complete data export feature" in prompt

    def test_moderate_level_includes_refocus(self) -> None:
        detector = DriftDetector("refactor payment module")
        prompt = detector.get_refocus_prompt(DriftLevel.MODERATE)
        assert "重新聚焦" in prompt

    def test_severe_level_includes_replan(self) -> None:
        detector = DriftDetector("fix critical bug")
        prompt = detector.get_refocus_prompt(DriftLevel.SEVERE)
        assert "紧急重新规划" in prompt


class TestDetectLoop:
    def test_no_loop_with_short_history(self) -> None:
        detector = DriftDetector("goal", similarity_window=5)
        detector._action_history = ["a", "b", "c"]
        assert detector._detect_loop() is False

    def test_period_2_loop(self) -> None:
        detector = DriftDetector("goal", similarity_window=6)
        detector._action_history = ["A", "B", "A", "B", "A", "B"]
        assert detector._detect_loop() is True

    def test_period_3_loop(self) -> None:
        detector = DriftDetector("goal", similarity_window=6)
        detector._action_history = ["X", "Y", "Z", "X", "Y", "Z"]
        assert detector._detect_loop() is True

    def test_no_loop_varied_actions(self) -> None:
        detector = DriftDetector("goal", similarity_window=5)
        detector._action_history = ["alpha", "beta", "gamma", "delta", "epsilon"]
        assert detector._detect_loop() is False


class TestExtractKeywords:
    def test_extracts_chinese_keywords(self) -> None:
        keywords = _extract_keywords("implement user login feature")
        assert len(keywords) > 0
        assert "implement" in keywords
        # 停用词不应出现
        assert "的" not in keywords

    def test_extracts_english_keywords(self) -> None:
        keywords = _extract_keywords("implement user login feature")
        assert "implement" in keywords
        assert "user" in keywords
        assert "login" in keywords

    def test_filters_short_tokens(self) -> None:
        keywords = _extract_keywords("a b cd efg")
        # 单字符不应出现
        assert "a" not in keywords
        assert "b" not in keywords

    def test_empty_text(self) -> None:
        keywords = _extract_keywords("")
        assert keywords == set()

    def test_filters_pure_digits(self) -> None:
        keywords = _extract_keywords("version 123 build 456")
        assert "123" not in keywords
        assert "456" not in keywords


class TestStringSimilarity:
    def test_identical_strings(self) -> None:
        assert _string_similarity("hello", "hello") == 1.0

    def test_empty_string(self) -> None:
        assert _string_similarity("", "hello") == 0.0
        assert _string_similarity("hello", "") == 0.0

    def test_both_empty(self) -> None:
        assert _string_similarity("", "") == 0.0

    def test_similar_strings(self) -> None:
        sim = _string_similarity("abcdef", "abcxyz")
        assert 0.0 < sim < 1.0

    def test_completely_different(self) -> None:
        sim = _string_similarity("aaa", "zzz")
        assert sim < 0.5


class TestComputeRelevance:
    def test_no_goal_keywords_returns_neutral(self) -> None:
        detector = DriftDetector("")
        relevance = detector._compute_relevance("any action")
        assert relevance == 0.5

    def test_no_action_keywords_returns_low(self) -> None:
        detector = DriftDetector("implement login feature")
        relevance = detector._compute_relevance("")
        assert relevance == 0.3

    def test_high_overlap_returns_high_relevance(self) -> None:
        detector = DriftDetector("user login feature implementation")
        relevance = detector._compute_relevance("implementing the user login feature")
        assert relevance > 0.4

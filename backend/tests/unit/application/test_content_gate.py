"""content/gate 模块测试 (T4/B方案) — 门禁内容显性化 + GATE_EVALUATION_PROMPT。

验证 GateProfile/PROFILES/get_profile + GATE_EVALUATION_PROMPT 从 gate_threshold/pipeline
迁入 content 模块后:
- GATE_EVALUATION_PROMPT format 占位符完整 (逐字迁移正确性)
- PROFILES 关键阈值 (free≥5/moderate≥6/strict≥7) + get_profile .get fallback

注: PROFILES/get_profile 的完整行为由 test_gate_threshold.py 覆盖 (已改读 content),
本文件聚焦 GATE_EVALUATION_PROMPT + content 模块整体。
"""

from __future__ import annotations

from arc.application.context.content.gate import (
    GATE_EVALUATION_PROMPT,
    PROFILES,
    get_profile,
)
from arc.domain.project.value_objects import ProcessConstraint


class TestGateEvaluationPrompt:
    """GATE_EVALUATION_PROMPT — format 占位符完整 (迁自 pipeline/prompts)。"""

    def test_has_placeholders(self):
        assert "{phase_label}" in GATE_EVALUATION_PROMPT
        assert "{artifact_content}" in GATE_EVALUATION_PROMPT
        assert "{charter_section}" in GATE_EVALUATION_PROMPT
        assert "{conventions_section}" in GATE_EVALUATION_PROMPT
        assert "{capabilities_section}" in GATE_EVALUATION_PROMPT

    def test_format_works(self):
        result = GATE_EVALUATION_PROMPT.format(
            phase_label="需求澄清",
            artifact_content="{}",
            charter_section="",
            conventions_section="",
            capabilities_section="",
        )
        assert "需求澄清" in result
        assert "passed" in result
        assert "score" in result


class TestProfilesSanity:
    """PROFILES 关键阈值 sanity (完整行为见 test_gate_threshold)。"""

    def test_score_thresholds(self):
        assert get_profile(ProcessConstraint.FREE).score_threshold == 5
        assert get_profile(ProcessConstraint.MODERATE).score_threshold == 6
        assert get_profile(ProcessConstraint.STRICT).score_threshold == 7

    def test_all_constraints_registered(self):
        for c in ProcessConstraint:
            assert c in PROFILES

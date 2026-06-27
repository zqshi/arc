"""content/phase_prompts 模块测试 (T3/B方案) — 阶段 prompt 内容显性化 + .get fallback。

验证 phase system/extraction prompt + phase inference prompt 从 pipeline/prompts.py
+ prompt_builder.py 迁入 content 模块后:
- PHASE_SYSTEM_PROMPTS / PHASE_EXTRACTION_PROMPTS 全 phase 注册 (7 phase), .get fallback
- _PHASE_INFERENCE_PROMPT format 占位符完整 (逐字迁移正确性)
"""

from __future__ import annotations

from arc.application.context.content.phase_prompts import (
    PHASE_EXTRACTION_PROMPTS,
    PHASE_SYSTEM_PROMPTS,
    _PHASE_INFERENCE_PROMPT,
)
from arc.domain.pipeline.value_objects import PhaseType


class TestPhaseSystemPrompts:
    """phase system prompt 注册表 — 全 phase 注册 + .get fallback。"""

    def test_all_phases_registered(self):
        for phase in PhaseType:
            assert PHASE_SYSTEM_PROMPTS.get(phase, "") != "", f"{phase} system prompt 缺失"

    def test_clarification_has_title_placeholder(self):
        assert "{title}" in PHASE_SYSTEM_PROMPTS[PhaseType.CLARIFICATION]

    def test_architecture_has_requirement_and_ui_design_placeholders(self):
        prompt = PHASE_SYSTEM_PROMPTS[PhaseType.ARCHITECTURE]
        assert "{requirement_spec}" in prompt
        assert "{ui_design}" in prompt


class TestPhaseExtractionPrompts:
    """phase extraction prompt 注册表 — 全 phase 注册 + .get fallback。"""

    def test_all_phases_registered(self):
        for phase in PhaseType:
            assert PHASE_EXTRACTION_PROMPTS.get(phase, "") != "", f"{phase} extraction prompt 缺失"

    def test_clarification_has_json_contract(self):
        assert "```json" in PHASE_EXTRACTION_PROMPTS[PhaseType.CLARIFICATION]

    def test_architecture_extraction_has_data_model(self):
        assert "data_model" in PHASE_EXTRACTION_PROMPTS[PhaseType.ARCHITECTURE]


class TestPhaseInferencePrompt:
    """phase inference prompt — format 占位符完整 (迁自 prompt_builder)。"""

    def test_has_completed_and_prefilter_placeholders(self):
        assert "{completed}" in _PHASE_INFERENCE_PROMPT
        assert "{prefilter}" in _PHASE_INFERENCE_PROMPT

    def test_format_works(self):
        result = _PHASE_INFERENCE_PROMPT.format(completed="a,b", prefilter="development")
        assert "a,b" in result
        assert "development" in result

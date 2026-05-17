"""Phase gate evaluation — quality checks before advancing to next phase."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from arc.application.ai.json_extract import extract_json
from arc.application.pipeline.prompts import (
    GATE_EVALUATION_PROMPT,
    PHASE_REQUIRED_FIELDS,
    PHASES_NO_SKIP,
)
from arc.domain.pipeline.value_objects import PhaseType

logger = logging.getLogger(__name__)

PHASE_LABELS: dict[PhaseType, str] = {
    PhaseType.CLARIFICATION: "需求澄清",
    PhaseType.UI_DESIGN: "UI/UX设计",
    PhaseType.ARCHITECTURE: "技术架构",
    PhaseType.DEVELOPMENT: "开发实现",
    PhaseType.TESTING: "测试验证",
    PhaseType.DEPLOYMENT: "部署上线",
    PhaseType.EXTRACTION: "经验沉淀",
}


@dataclass
class GateResult:
    passed: bool
    score: int
    gaps: list[str]
    suggestion: str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "gaps": self.gaps,
            "suggestion": self.suggestion,
        }


class PhaseGateError(Exception):
    def __init__(self, result: GateResult):
        self.result = result
        super().__init__(f"Gate check failed: {result.suggestion}")


def check_required_fields(phase_type: PhaseType, content: dict) -> list[str]:
    """Check that all required fields exist and have non-trivial content."""
    required = PHASE_REQUIRED_FIELDS.get(phase_type, [])
    gaps = []
    for field in required:
        value = content.get(field)
        if value is None:
            gaps.append(f"缺少必填字段「{field}」")
        elif isinstance(value, str) and (
            not value.strip()
            or value.strip() in ("待补充", "未定义", "暂无", "（尚未生成）", "N/A")
        ):
            gaps.append(f"字段「{field}」内容为空或占位符")
        elif isinstance(value, list) and len(value) == 0:
            gaps.append(f"字段「{field}」列表为空")
    return gaps


def can_skip(phase_type: PhaseType) -> bool:
    return phase_type not in PHASES_NO_SKIP


async def evaluate_gate(phase_type: PhaseType, content: dict) -> GateResult:
    """Full gate evaluation: structural check + LLM quality assessment."""
    structural_gaps = check_required_fields(phase_type, content)

    if len(structural_gaps) >= 3:
        return GateResult(
            passed=False,
            score=2,
            gaps=structural_gaps,
            suggestion="产出物缺少多个关键字段，请继续与AI对话补充信息后重新生成。",
        )

    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.ai.resilience import create_resilient_adapter

    phase_label = PHASE_LABELS.get(phase_type, phase_type.value)
    prompt = GATE_EVALUATION_PROMPT.format(
        phase_label=phase_label,
        artifact_content=json.dumps(content, ensure_ascii=False, indent=2),
    )

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat([
            LLMMessage(role="user", content=prompt),
        ])
    finally:
        await adapter.close()

    result_data = extract_json(response.content)
    if not isinstance(result_data, dict):
        logger.warning("Gate evaluation parse failed, blocking advancement")
        return GateResult(
            passed=False,
            score=4,
            gaps=structural_gaps or ["AI质量评审结果解析失败"],
            suggestion="质量评审遇到问题，请重试。如持续失败请检查AI服务状态。",
        )

    all_gaps = list(set(structural_gaps + result_data.get("gaps", [])))
    passed = result_data.get("passed", False) and len(structural_gaps) == 0
    score = result_data.get("score", 5)

    if score < 7:
        passed = False

    return GateResult(
        passed=passed,
        score=score,
        gaps=all_gaps,
        suggestion=result_data.get("suggestion", "请补充完善产出物内容。"),
    )

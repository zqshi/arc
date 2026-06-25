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


async def evaluate_gate(
    phase_type: PhaseType,
    content: dict,
    conventions: str = "",
    *,
    prior_artifacts: dict | None = None,
) -> GateResult:
    """Full gate evaluation: structural check + methodology validation + LLM quality assessment.

    Args:
        prior_artifacts: 已确认的前置阶段产出物，用于交叉一致性检查。
                        key=artifact_type (str), value=content (dict)
    """
    structural_gaps = check_required_fields(phase_type, content)

    # --- 方法论校验 (DDD / ADR) ---
    methodology_gaps = _check_methodology(phase_type, content)
    structural_gaps.extend(methodology_gaps)

    # --- 交叉一致性检查 ---
    if prior_artifacts:
        cross_gaps = _check_cross_consistency(phase_type, content, prior_artifacts)
        structural_gaps.extend(cross_gaps)

    if len(structural_gaps) >= 3:
        return GateResult(
            passed=False,
            score=2,
            gaps=structural_gaps,
            suggestion="产出物缺少多个关键字段或未通过方法论校验，请继续完善。",
        )

    from arc.application.ai.llm_adapter import LLMMessage
    from arc.application.ai.resilience import create_resilient_adapter

    phase_label = PHASE_LABELS.get(phase_type, phase_type.value)

    conventions_section = ""
    if conventions.strip():
        conventions_section = f"\n## 项目规范（产出物必须符合以下规范）:\n{conventions}\n"

    prompt = GATE_EVALUATION_PROMPT.format(
        phase_label=phase_label,
        artifact_content=json.dumps(content, ensure_ascii=False, indent=2),
        conventions_section=conventions_section,
    )

    adapter = create_resilient_adapter()
    try:
        response = await adapter.chat(
            [
                LLMMessage(role="user", content=prompt),
            ]
        )
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


# ---------------------------------------------------------------------------
# 方法论校验 (Skill 集成)
# ---------------------------------------------------------------------------


def _check_methodology(phase_type: PhaseType, content: dict) -> list[str]:
    """根据阶段执行方法论专项校验。"""
    gaps = []

    if phase_type == PhaseType.ARCHITECTURE:
        from arc.application.execution.architecture_methodology import validate_architecture

        result = validate_architecture(content)
        gaps.extend(result.violations)
        # warnings 不阻断，仅记录
        for w in result.warnings:
            logger.info("Architecture gate warning: %s", w)

    elif phase_type == PhaseType.CLARIFICATION:
        # 需求规格交叉自洽性检查
        user_stories = content.get("user_stories", [])
        target_users = content.get("target_users", [])
        ac = content.get("acceptance_criteria", [])

        if user_stories and target_users:
            user_types = {u.get("type", "") for u in target_users if isinstance(u, dict)}
            story_roles = {s.get("role", "") for s in user_stories if isinstance(s, dict)}
            uncovered = user_types - story_roles - {""}
            if uncovered:
                gaps.append(f"用户故事未覆盖目标用户: {', '.join(uncovered)}")

        if user_stories and ac:
            story_count = len([
                s for s in user_stories
                if isinstance(s, dict) and s.get("priority") == "P0"
            ])
            ac_count = len(ac)
            if story_count > 0 and ac_count < story_count:
                gaps.append(f"验收标准({ac_count}条)少于P0用户故事({story_count}条)，可能覆盖不足")

    elif phase_type == PhaseType.UI_DESIGN:
        from arc.application.execution.ui_design_methodology import validate_ui_design

        ui_gaps = validate_ui_design(content)
        gaps.extend(ui_gaps)

    elif phase_type == PhaseType.DEVELOPMENT:
        from arc.application.execution.dev_test_methodology import validate_development

        dev_gaps = validate_development(content)
        gaps.extend(dev_gaps)

    elif phase_type == PhaseType.TESTING:
        from arc.application.execution.dev_test_methodology import validate_testing

        test_gaps = validate_testing(content)
        gaps.extend(test_gaps)

    return gaps


def _check_cross_consistency(
    phase_type: PhaseType,
    content: dict,
    prior_artifacts: dict,
) -> list[str]:
    """跨阶段交叉一致性检查。"""
    gaps = []

    if phase_type == PhaseType.ARCHITECTURE:
        # 检查 API 是否覆盖了需求中的用户故事
        req_spec = prior_artifacts.get("requirement_spec", {})
        stories = req_spec.get("user_stories", []) if isinstance(req_spec, dict) else []
        api_design = content.get("api_design", [])

        if stories and isinstance(api_design, list):
            p0_stories = [s for s in stories if isinstance(s, dict) and s.get("priority") == "P0"]
            if p0_stories and len(api_design) < len(p0_stories):
                gaps.append(
                    f"API 端点({len(api_design)}个)少于P0用户故事({len(p0_stories)}个)，"
                    "可能有功能未覆盖"
                )

    elif phase_type == PhaseType.TESTING:
        # 检查测试是否逐条覆盖了验收标准
        req_spec = prior_artifacts.get("requirement_spec", {})
        acs = req_spec.get("acceptance_criteria", []) if isinstance(req_spec, dict) else []
        verifications = content.get("criteria_verification", [])

        if acs and verifications:
            ac_ids = {ac.get("id", "") for ac in acs if isinstance(ac, dict)} - {""}
            verified_criteria = set()
            for v in verifications:
                if isinstance(v, dict):
                    criteria_text = v.get("criteria", "")
                    for ac_id in ac_ids:
                        if ac_id in criteria_text:
                            verified_criteria.add(ac_id)
            unverified = ac_ids - verified_criteria
            if unverified:
                gaps.append(f"验收标准未被测试覆盖: {', '.join(sorted(unverified))}")

    return gaps

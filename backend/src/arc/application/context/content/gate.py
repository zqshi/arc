"""gate 内容显性化 (B方案/T4) — 门禁检查项集中声明。

纯内容 (GateProfile 阈值 profile + gate 评估 prompt) 从 execution/gate_threshold.py
+ pipeline/prompts.py 迁入此模块, 消费方 (conversation_gate / pipeline/gate /
artifact_extractor) 改读本模块。4 层评估流程 (结构→方法论→一致性→LLM) 是编排逻辑, 保留原模块。
DELIVERABLE_REQUIRED_FIELDS 留 domain (artifact 字段约束 = domain 知识, 不跨层)。

复用 v6.9 dict + .get(key, default) fallback 模式。
"""

from __future__ import annotations

from dataclasses import dataclass

from arc.domain.project.value_objects import ProcessConstraint


@dataclass(frozen=True)
class GateProfile:
    """某个 constraint 级别下的门禁行为参数。"""

    score_threshold: int  # LLM 质量评审通过分数 (free≥5 / moderate≥6 / strict≥7)
    enable_methodology: bool  # 是否跑方法论校验 (free=False，轻量)
    enable_cross_check: bool  # 是否跑交叉一致性 (三模式都 True)
    enable_llm_review: bool  # 是否跑 LLM 质量评审 (三模式都 True)
    structural_short_circuit: int  # 结构缺口≥N 直接判失败不调 LLM (省成本)
    dependency_block_mode: str  # "hard" 硬阻断 | "soft" 软警告
    # 即便 soft 模式也硬阻断的交付物 (没需求没法提炼经验 / 没代码没法部署)
    dependency_hard_block: tuple[str, ...]


PROFILES: dict[ProcessConstraint, GateProfile] = {
    ProcessConstraint.FREE: GateProfile(
        score_threshold=5,
        enable_methodology=False,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=5,
        dependency_block_mode="soft",
        dependency_hard_block=("experience_card", "deploy_report"),
    ),
    ProcessConstraint.MODERATE: GateProfile(
        score_threshold=6,
        enable_methodology=True,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=4,
        dependency_block_mode="hard",
        dependency_hard_block=(),
    ),
    ProcessConstraint.STRICT: GateProfile(
        score_threshold=7,
        enable_methodology=True,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=3,
        dependency_block_mode="hard",
        dependency_hard_block=(),
    ),
}


def get_profile(constraint: ProcessConstraint) -> GateProfile:
    """查询 constraint 对应的门禁参数，未知值降级到 free。"""
    return PROFILES.get(constraint, PROFILES[ProcessConstraint.FREE])


GATE_EVALUATION_PROMPT = """\
评估这个阶段的产出物质量是否足以推进。

阶段: {phase_label}
产出物:
```json
{artifact_content}
```
{charter_section}
{conventions_section}
{capabilities_section}

输出 JSON:
```json
{{
  "passed": true/false,
  "score": 1-10,
  "gaps": ["具体缺失或不足"],
  "suggestion": "一句话建议"
}}
```"""

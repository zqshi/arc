"""门禁阈值注册表 — 按 ProcessConstraint 分级的门禁参数。

集中 score 阈值 / 方法论开关 / 交叉检查 / 依赖阻断模式，按 constraint 查询，
不在 service 里写 if constraint 分支 (满足 CLAUDE.md 分层约束)。

元原则: 质量底线门禁——所有模式都过门禁，只是严格度分级。
free/moderate/strict 的差异在"门禁严格度"，不在"是否过门禁"。
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

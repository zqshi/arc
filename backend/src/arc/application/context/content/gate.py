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
    """某个 constraint 级别下的门禁行为参数。

    依赖约束 (DAG 前置满足) 不在此 profile — 它是三档共享的硬不变量,
    由 dependency_graph + artifact_extractor 统一硬阻断, 与 constraint 无关。
    """

    score_threshold: int  # LLM 质量评审通过分数 (free≥5 / moderate≥6 / strict≥7)
    enable_methodology: bool  # 是否跑方法论校验 (free=False，轻量)
    enable_cross_check: bool  # 是否跑交叉一致性 (三模式都 True)
    enable_llm_review: bool  # 是否跑 LLM 质量评审 (三模式都 True)
    structural_short_circuit: int  # 结构缺口≥N 直接判失败不调 LLM (省成本)


PROFILES: dict[ProcessConstraint, GateProfile] = {
    ProcessConstraint.FREE: GateProfile(
        score_threshold=5,
        enable_methodology=False,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=5,
    ),
    ProcessConstraint.MODERATE: GateProfile(
        score_threshold=6,
        enable_methodology=True,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=4,
    ),
    ProcessConstraint.STRICT: GateProfile(
        score_threshold=7,
        enable_methodology=True,
        enable_cross_check=True,
        enable_llm_review=True,
        structural_short_circuit=3,
    ),
}


def get_profile(constraint: ProcessConstraint) -> GateProfile:
    """查询 constraint 对应的门禁参数，未知值降级到 free。"""
    return PROFILES.get(constraint, PROFILES[ProcessConstraint.FREE])


GATE_EVALUATION_PROMPT = """\
评估「{phase_label}」阶段产出物质量。仅基于产出物客观内容评分，不要因"可以更好"而压分。

产出物:
```json
{artifact_content}
```
{charter_section}
{conventions_section}
{capabilities_section}

## 评分维度（综合分 = 加权平均，四舍五入到整数）
- 完整性 (0.30): 必填字段齐全、内容实质（非占位符）、覆盖该阶段应交付的关键决策
- 一致性 (0.25): 内部自洽，与前置产出物/项目规范/宪章治理意图不矛盾
- 可行性 (0.25): 技术方案可落地、验收标准可验证、无空中楼阁
- 清晰度 (0.20): 表述明确无歧义、粒度合适、可被下游阶段直接消费

## 综合分锚点
- 9-10: 各维度无明显短板，可直接推进下一阶段
- 7-8: 主要维度达标，有小瑕疵但不影响推进
- 5-6: 部分维度不足，需补充但方向正确
- 3-4: 多个维度明显不足
- 1-2: 产出物基本不可用

## gap 分级（阻断性 vs 改进性必须分开）
- p0_gaps: 阻断性缺口 — 不补会直接导致后续阶段失败（缺关键字段/自相矛盾/不可落地）
- gaps: 改进建议 — 锦上添花，非阻断

## 评分规则
综合分 >=7 即达标。不要因 gaps（改进建议）压低综合分；只有 p0_gaps（阻断性缺口）才应反映到分数。
不要输出 passed 字段 — 是否推进由系统按综合分 + p0_gaps 判定。

输出 JSON:
```json
{{
  "score": 1-10,
  "p0_gaps": ["阻断性缺口"],
  "gaps": ["改进建议"],
  "suggestion": "一句话建议"
}}
```"""

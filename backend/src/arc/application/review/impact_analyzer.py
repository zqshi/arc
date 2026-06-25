"""ImpactAnalyzer — 分析领域模型变更对进行中需求的影响。

核心逻辑:
1. 找出所有 ACTIVE 状态的 Todo
2. 每个 Todo 的交付物中引用了哪些聚合
3. 与受影响聚合取交集
4. 根据 Todo 当前阶段 × 变更类型 判断风险等级
"""

from __future__ import annotations

import uuid

from arc.application.review.aggregate_extractor import extract_aggregate_references
from arc.domain.artifact.repository import ArtifactRepository
from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.review.value_objects import (
    ImpactItem,
    ImpactReport,
    ModelChangeScope,
    RiskLevel,
)
from arc.domain.todo.repository import ITodoRepository
from arc.domain.todo.value_objects import TodoStatus

# ── 风险矩阵 ──────────────────────────────────────────────
#
# Todo 当前阶段 × 模型变更类型 → 风险等级
#
# 核心思想:
# - 越早的阶段越安全（模型还没固化到代码）
# - breaking 变更永远比 additive 危险
# - development+ 阶段遇到 structural/breaking 必须高风险

_RISK_MATRIX: dict[tuple[str, ModelChangeScope], RiskLevel] = {
    # clarification: 还在讨论阶段，模型变了直接用新的
    (PhaseType.CLARIFICATION, ModelChangeScope.ADDITIVE): RiskLevel.NONE,
    (PhaseType.CLARIFICATION, ModelChangeScope.STRUCTURAL): RiskLevel.NONE,
    (PhaseType.CLARIFICATION, ModelChangeScope.BREAKING): RiskLevel.LOW,
    # ui_design: 不涉及数据模型
    (PhaseType.UI_DESIGN, ModelChangeScope.ADDITIVE): RiskLevel.NONE,
    (PhaseType.UI_DESIGN, ModelChangeScope.STRUCTURAL): RiskLevel.NONE,
    (PhaseType.UI_DESIGN, ModelChangeScope.BREAKING): RiskLevel.LOW,
    # architecture: 正在设计数据模型，可能需要修改交付物
    (PhaseType.ARCHITECTURE, ModelChangeScope.ADDITIVE): RiskLevel.LOW,
    (PhaseType.ARCHITECTURE, ModelChangeScope.STRUCTURAL): RiskLevel.MEDIUM,
    (PhaseType.ARCHITECTURE, ModelChangeScope.BREAKING): RiskLevel.HIGH,
    # development: 代码已基于旧模型
    (PhaseType.DEVELOPMENT, ModelChangeScope.ADDITIVE): RiskLevel.LOW,
    (PhaseType.DEVELOPMENT, ModelChangeScope.STRUCTURAL): RiskLevel.HIGH,
    (PhaseType.DEVELOPMENT, ModelChangeScope.BREAKING): RiskLevel.CRITICAL,
    # testing: 测试用例基于旧模型
    (PhaseType.TESTING, ModelChangeScope.ADDITIVE): RiskLevel.LOW,
    (PhaseType.TESTING, ModelChangeScope.STRUCTURAL): RiskLevel.HIGH,
    (PhaseType.TESTING, ModelChangeScope.BREAKING): RiskLevel.CRITICAL,
    # deployment: 已经到上线阶段
    (PhaseType.DEPLOYMENT, ModelChangeScope.ADDITIVE): RiskLevel.MEDIUM,
    (PhaseType.DEPLOYMENT, ModelChangeScope.STRUCTURAL): RiskLevel.CRITICAL,
    (PhaseType.DEPLOYMENT, ModelChangeScope.BREAKING): RiskLevel.CRITICAL,
    # extraction: 经验沉淀，影响最小
    (PhaseType.EXTRACTION, ModelChangeScope.ADDITIVE): RiskLevel.NONE,
    (PhaseType.EXTRACTION, ModelChangeScope.STRUCTURAL): RiskLevel.LOW,
    (PhaseType.EXTRACTION, ModelChangeScope.BREAKING): RiskLevel.LOW,
}

_RISK_RECOMMENDATIONS: dict[RiskLevel, str] = {
    RiskLevel.NONE: "无影响，可安全升级",
    RiskLevel.LOW: "影响较小，升级后通知开发者即可",
    RiskLevel.MEDIUM: "需审视当前阶段交付物，可能需要修改",
    RiskLevel.HIGH: "建议暂停此需求，等待模型升级完成后再继续",
    RiskLevel.CRITICAL: "必须阻断此需求，模型升级前不得继续推进",
}


def assess_risk(phase: str | None, scope: ModelChangeScope) -> RiskLevel:
    """根据阶段和变更类型评估风险。"""
    if not phase:
        return RiskLevel.LOW
    key = (phase, scope)
    return _RISK_MATRIX.get(key, RiskLevel.MEDIUM)


def risk_recommendation(risk: RiskLevel) -> str:
    """获取风险等级对应的处理建议。"""
    return _RISK_RECOMMENDATIONS.get(risk, "请评估影响后决定")


class ImpactAnalyzer:
    """领域模型变更影响分析器。"""

    def __init__(
        self,
        todo_repo: ITodoRepository,
        artifact_repo: ArtifactRepository,
    ):
        self._todo_repo = todo_repo
        self._artifact_repo = artifact_repo

    async def analyze(
        self,
        project_id: uuid.UUID,
        affected_aggregates: list[str],
        change_scope: ModelChangeScope,
    ) -> ImpactReport:
        """分析模型变更对进行中需求的影响。

        Args:
            project_id: 项目 ID
            affected_aggregates: 受影响的聚合名称列表
            change_scope: 变更范围 (additive/structural/breaking)

        Returns:
            ImpactReport 包含受影响的 todos 和风险评估
        """
        if not affected_aggregates:
            return ImpactReport(
                project_id=project_id,
                affected_aggregates=(),
                change_scope=change_scope,
                summary="无受影响的聚合",
            )

        affected_set = set(affected_aggregates)

        # 1. 获取项目下所有 todos，过滤 ACTIVE 状态
        all_todos, _ = await self._todo_repo.list_all(
            project_id=project_id, limit=500,
        )
        active_todos = [t for t in all_todos if t.status == TodoStatus.ACTIVE]

        if not active_todos:
            return ImpactReport(
                project_id=project_id,
                affected_aggregates=tuple(affected_aggregates),
                change_scope=change_scope,
                summary="无进行中的需求",
            )

        # 2. 对每个 todo 检查交付物中的聚合引用
        items: list[ImpactItem] = []
        for todo in active_todos:
            artifacts = await self._artifact_repo.list_by_todo_id(todo.id)
            artifact_dicts = [{"content": a.content} for a in artifacts]
            referenced = extract_aggregate_references(artifact_dicts)

            overlap = affected_set & referenced
            if not overlap:
                continue

            phase_str = todo.current_phase.value if todo.current_phase else None
            risk = assess_risk(phase_str, change_scope)
            rec = risk_recommendation(risk)

            items.append(ImpactItem(
                todo_id=todo.id,
                todo_title=todo.title,
                current_phase=phase_str or "unknown",
                affected_aggregates=tuple(sorted(overlap)),
                risk=risk,
                recommendation=rec,
            ))

        # 3. 构建报告
        items.sort(key=lambda x: x.risk, reverse=True)
        summary = _build_summary(items, affected_aggregates, change_scope)

        return ImpactReport(
            project_id=project_id,
            affected_aggregates=tuple(affected_aggregates),
            change_scope=change_scope,
            items=tuple(items),
            summary=summary,
        )


def _build_summary(
    items: list[ImpactItem],
    aggregates: list[str],
    scope: ModelChangeScope,
) -> str:
    """生成影响报告摘要。"""
    if not items:
        return f"变更涉及 {len(aggregates)} 个聚合，无进行中需求受影响"

    high_count = sum(1 for i in items if i.risk >= RiskLevel.HIGH)
    total = len(items)

    parts = [f"变更类型: {scope.value}，涉及 {len(aggregates)} 个聚合，影响 {total} 个进行中需求"]
    if high_count > 0:
        parts.append(f"其中 {high_count} 个需求风险较高，建议暂停")
    return "。".join(parts)

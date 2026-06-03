"""规划上下文构建 — 为规划引擎提供智能上下文注入。

从 planning_service.py 提取。职责：
- 历史经验上下文构建（估算偏差、范围变更、技术决策）
- 领域模型上下文格式化
- 估算校准表格生成
- 通用格式化工具（约束、状态、数字提取）
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def build_planning_experience_context(
    db: AsyncSession, project_id: uuid.UUID
) -> str:
    """构建规划阶段的经验上下文 — 估算偏差、范围变更、技术决策。"""
    from arc.application.experience.scorer import MemoryScorer
    from arc.infrastructure.repositories.experience import ExperienceRepository

    try:
        exp_repo = ExperienceRepository(db)
        all_exps = await exp_repo.list_by_project_id(project_id, limit=30)
        if not all_exps:
            return ""

        # 提取估算校准数据 — 结构化表格
        estimation_exps = [
            e for e in all_exps if e.category.value == "estimation"
        ]
        calibration_section = format_estimation_calibration(estimation_exps)

        # 取规划相关经验
        planning_categories = {"estimation", "scope_change", "architecture_decision"}
        planning_exps = [
            e for e in all_exps
            if e.category.value in planning_categories
        ]
        if len(planning_exps) < 5:
            other = [e for e in all_exps if e not in planning_exps]
            planning_exps.extend(other[: 5 - len(planning_exps)])

        if not planning_exps and not calibration_section:
            return ""

        scorer = MemoryScorer()
        scored = scorer.score_batch(planning_exps)
        top_k = scored[:5]

        parts = ["## 历史经验（基于本项目过往迭代）\n"]

        # 估算校准表格优先展示
        if calibration_section:
            parts.append(calibration_section)
            parts.append("")

        parts.append(
            "### 经验教训\n"
            "以下是过往版本的具体经验，规划时参考：\n"
        )
        for exp, score in top_k:
            if score < 0.1:
                continue
            parts.append(f"**{exp.title}**")
            parts.append(f"- 问题: {exp.problem}")
            parts.append(f"- 方案: {exp.solution}")
            if exp.applicable_scenarios:
                parts.append(f"- 适用场景: {exp.applicable_scenarios}")
            parts.append("")

        return "\n".join(parts) if len(parts) > 2 else ""
    except Exception:
        return ""


def format_estimation_calibration(estimation_exps: list) -> str:
    """将估算类经验格式化为校准表格 — 让 AI 看到历史偏差趋势。"""
    if not estimation_exps:
        return ""

    parts = [
        "### 估算校准数据\n",
        "以下是本项目历史版本的规划 vs 实际交付数据，"
        "请据此校准本次规划的颗粒度和工作量估算：\n",
        "| 版本 | 规划数 | 完成数 | 完成率 | 教训 |",
        "|------|--------|--------|--------|------|",
    ]

    for exp in estimation_exps[-5:]:  # 最近 5 个版本
        problem = exp.problem or ""
        solution = exp.solution or ""

        planned = _extract_number(problem, "规划")
        delivered = _extract_number(problem, "交付") or _extract_number(solution, "总计")
        rate = ""
        if "完成率" in solution:
            m = re.search(r"完成率\s*(\d+%)", solution)
            if m:
                rate = m.group(1)

        title_short = exp.title.replace("版本 ", "").replace(" 交付偏差", "")
        lesson = ""
        if exp.applicable_scenarios:
            lesson = exp.applicable_scenarios[:30]

        parts.append(
            f"| {title_short} | {planned or '?'} | {delivered or '?'} "
            f"| {rate or '?'} | {lesson} |"
        )

    return "\n".join(parts)


async def build_domain_model_context(
    db: AsyncSession, project_id: uuid.UUID
) -> str:
    """构建领域模型上下文 — 让规划理解架构现实。"""
    from arc.infrastructure.repositories.project import ProjectRepository

    try:
        project_repo = ProjectRepository(db)
        project = await project_repo.get_by_id(project_id)
        if not project or not project.domain_model:
            return ""

        dm = project.domain_model
        subdomains = dm.get("subdomains", [])
        aggregates = dm.get("aggregates", [])
        relations = dm.get("aggregate_relations", []) or dm.get("relations", [])

        if not aggregates and not subdomains:
            return ""

        parts = ["## 当前架构现实（领域模型）\n"]
        parts.append(
            "以下是项目当前的领域模型，规划新功能时请考虑：\n"
            "- 新功能涉及哪些已有聚合？扩展现有聚合 vs 新增聚合的复杂度差异\n"
            "- 跨聚合的功能通常比单聚合内功能更复杂\n"
            "- 新增子域意味着更高的架构风险\n"
        )

        if subdomains:
            parts.append("### 子域划分")
            for sd in subdomains:
                parts.append(
                    f"- **{sd.get('name', '')}** ({sd.get('type', '')}):"
                    f" {sd.get('description', '')}"
                )
            parts.append("")

        if aggregates:
            parts.append("### 聚合 (Aggregates)")
            for agg in aggregates[:15]:
                ctx = agg.get("context", "")
                ctx_label = f" [{ctx}]" if ctx else ""
                entities = agg.get("entities", [])
                entity_names = ", ".join(entities[:5]) if entities else ""
                parts.append(
                    f"- **{agg.get('name', '')}**{ctx_label}: "
                    f"{agg.get('description', '')}"
                    + (f" (实体: {entity_names})" if entity_names else "")
                )
            parts.append("")

        if relations:
            parts.append("### 聚合间关系")
            for rel in relations[:10]:
                parts.append(
                    f"- {rel.get('from', '')} → {rel.get('to', '')} "
                    f"[{rel.get('type', '')}]: {rel.get('description', '')}"
                )
            parts.append("")

        return "\n".join(parts)
    except Exception:
        return ""


def format_constraints(constraints: dict) -> str:
    """格式化规划约束条件。"""
    if not constraints:
        return "无特定约束，使用合理默认值（2周迭代，3人团队）"
    parts = []
    if "team_capacity" in constraints:
        parts.append(f"- 团队规模: {constraints['team_capacity']}人")
    if "iteration_weeks" in constraints:
        parts.append(f"- 迭代周期: {constraints['iteration_weeks']}周/迭代")
    if "hard_deadlines" in constraints:
        for dl in constraints["hard_deadlines"]:
            parts.append(f"- 硬截止: {dl}")
    if "release_strategy" in constraints:
        parts.append(f"- 发布策略偏好: {constraints['release_strategy']}")
    if "priority_framework" in constraints:
        parts.append(f"- 优先级框架: {constraints['priority_framework']}")
    return "\n".join(parts) if parts else "无特定约束"


def format_todo_status(todos: list) -> str:
    """格式化需求状态列表。"""
    if not todos:
        return "暂无需求"
    lines = []
    for t in todos:
        status_label = {
            "pending": "待启动",
            "active": "进行中",
            "done": "已完成",
            "error": "异常",
        }.get(t.status.value, t.status.value)
        phase_label = f" [{t.current_phase.value}]" if t.current_phase else ""
        lines.append(f"- [{status_label}]{phase_label} {t.title}")
    return "\n".join(lines)


def _extract_number(text: str, keyword: str) -> str | None:
    """从文本中提取关键词后面的数字。"""
    pattern = rf"{keyword}\s*(\d+)"
    m = re.search(pattern, text)
    return m.group(1) if m else None

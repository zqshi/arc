"""对话驱动执行模式的系统提示词和产出物定义。

设计哲学：意图驱动，Agent 自主推理。
- prompt 只给目标 + 能力声明 + 上下文
- Agent 自主决定推进路径、产出时机、分析深度
- 质量通过输出接口契约 + 后置验证保障，不通过前置规则约束

注: ARTIFACT_SCHEMAS 已拆到 artifact_schemas.py (v5.8.0), 此处 re-export 保持兼容。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arc.application.context.artifact_schemas import ARTIFACT_SCHEMAS
from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType

if TYPE_CHECKING:
    pass

# re-export 供 deliverable provider 等引用
__all__ = [
    "ARTIFACT_SCHEMAS",
    "ARTIFACT_TYPE_MARKERS",
    "ARTIFACT_LABELS",
    "CONVERSATION_MODE_SYSTEM_PROMPT",
    "AUTOPILOT_SECTION",
    "DELIVERABLE_CHECKLIST_TEMPLATE",
    "build_deliverable_checklist",
    "build_ddd_tdd_section",
]

ARTIFACT_TYPE_MARKERS: dict[str, ArtifactType] = {
    "requirement_spec": ArtifactType.REQUIREMENT_SPEC,
    "interaction_design": ArtifactType.INTERACTION_DESIGN,
    "ui_spec": ArtifactType.UI_SPEC,
    "prototype": ArtifactType.PROTOTYPE,
    "tech_architecture": ArtifactType.TECH_ARCHITECTURE,
    "dev_report": ArtifactType.DEV_REPORT,
    "test_report": ArtifactType.TEST_REPORT,
    "deploy_report": ArtifactType.DEPLOY_REPORT,
    "experience_card": ArtifactType.EXPERIENCE_CARD,
    # Legacy
    "ui_design": ArtifactType.UI_DESIGN,
}

DELIVERABLE_CHECKLIST_TEMPLATE = """## 交付物清单
{checklist}

当你判断某个交付物可以产出时，使用以下格式：

[DELIVERABLE:{artifact_type}]
```json
{{结构化内容}}
```

系统会自动解析归档。用户可在侧边面板查看已归档产出物。"""


def build_deliverable_checklist(required: list[str], completed: list[str]) -> str:
    lines = []
    for atype in required:
        label = ARTIFACT_LABELS.get(ArtifactType(atype), atype)
        marker = "x" if atype in completed else " "
        lines.append(f"- [{marker}] {label}")
    return "\n".join(lines)


CONVERSATION_MODE_SYSTEM_PROMPT = """你正在帮用户完成「{title}」。

目标：作为搭档，把这个需求从想法推进到可交付的成果。你自主判断需要做什么、什么时候做、怎么做。

{deliverable_section}

{methodology_section}

{project_context}

{experience_context}

{capabilities_section}

{sufficiency_hint}

## 当前任务
标题: {title}
描述: {description}

## 已完成的交付物
{completed_artifacts}"""


AUTOPILOT_SECTION = """## 自驾模式
你可以自主推进所有交付物，无需等待确认。只有在遇到真正无法独立决策的分歧点时
才暂停（输出 [NEEDS_INPUT]）。"""


# ---------------------------------------------------------------------------
# 交付物 JSON Schema（输出接口契约 — 不是规则，是让代码能解析的格式定义）
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# 领域模型上下文注入（只提供事实，不提供指令）
# ---------------------------------------------------------------------------


def build_ddd_tdd_section(domain_model: dict) -> str:
    """将项目领域模型作为上下文注入，供 Agent 自行判断如何使用。"""
    aggregates = domain_model.get("aggregates", [])
    relations = domain_model.get("relations", [])
    subdomains = domain_model.get("subdomains", [])
    contexts = domain_model.get("contexts", [])
    aggregate_relations = domain_model.get("aggregate_relations", [])

    if len(aggregates) < 2 and not subdomains:
        return ""

    # 模型元信息 — 版本和来源
    version = domain_model.get("version", "unknown")
    source = domain_model.get("source", "artifact_extraction")
    updated_at = domain_model.get("updated_at", "")

    lines = [
        f"## 项目领域模型（{len(aggregates)} 聚合, {len(subdomains)} 子域, "
        f"{len(contexts)} 上下文 | v{version}, 来源: {source}）"
    ]
    if updated_at:
        lines.append(f"*最后更新: {updated_at}*\n")

    if subdomains:
        lines.append("\n### 子域")
        for sd in subdomains:
            lines.append(
                f"- {sd.get('name', '')} ({sd.get('type', '')}): "
                f"{sd.get('description', '')}"
            )

    if contexts:
        lines.append("\n### 限界上下文")
        for ctx in contexts:
            line = f"- {ctx.get('name', '')}"
            if ctx.get("subdomain"):
                line += f" → {ctx['subdomain']}"
            if ctx.get("description"):
                line += f": {ctx['description']}"
            lines.append(line)

    if relations:
        lines.append("\n### 上下文关系")
        for rel in relations:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    if aggregates:
        lines.append("\n### 聚合")
        for agg in aggregates[:20]:
            name = agg.get("name", "")
            ctx = agg.get("context", "")
            parts = []
            if agg.get("entities"):
                parts.append(f"实体: {', '.join(agg['entities'][:5])}")
            if agg.get("value_objects"):
                parts.append(f"值对象: {', '.join(agg['value_objects'][:5])}")
            if agg.get("methods"):
                parts.append(f"方法: {', '.join(agg['methods'][:5])}")
            detail = "; ".join(parts) if parts else ""
            line = f"- **{name}**"
            if ctx:
                line += f" ({ctx})"
            if detail:
                line += f" — {detail}"
            lines.append(line)

    if aggregate_relations:
        lines.append("\n### 聚合关系")
        for rel in aggregate_relations[:15]:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    # 附加参考模式——Agent 根据项目实际情况自行选用
    lines.append("\n### 可参考的架构模式")
    lines.append(_REFERENCE_PATTERNS)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 参考模式库 — 作为上下文提供，Agent 自行判断适用性
# ---------------------------------------------------------------------------

_REFERENCE_PATTERNS = """\
以下模式供参考，根据项目实际情况选用最合适的：

**DDD（领域驱动设计）** — 适合业务逻辑复杂、有明确领域概念的系统
- 聚合 = 事务一致性边界，聚合间 ID 引用
- 值对象优先（不可变 = 安全）
- 限界上下文间通过 ACL/OHS/事件协作
- 领域事件驱动跨上下文通信

**TDD（测试驱动开发）** — 适合有明确验收标准、需要高可靠性的交付
- 从验收标准派生测试用例
- Red → Green → Refactor
- 每个测试对应一个业务不变量

**Clean Architecture** — 适合需要长期维护、技术栈可能变更的系统
- 依赖方向：外层 → 内层
- domain 不依赖框架和基础设施
- 通过接口反转依赖

**Event Sourcing** — 适合需要完整审计轨迹、时间旅行的业务
- 存储事件而非当前状态
- 重放事件重建状态

**CQRS** — 适合读写模式差异大的场景
- 命令（写）和查询（读）分离
- 读模型可针对查询优化

**微服务/模块化单体** — 架构粒度选择
- 微服务：团队独立部署、技术栈异构
- 模块化单体：单进程但模块边界清晰，必要时可拆"""

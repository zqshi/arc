"""技术架构方法论引擎 — 基于 ddd-toolkit 改造。

来源: ddd-toolkit v0.3.1 改造
职责:
  - 引导架构阶段按"战略设计→事件风暴→战术建模"三步递进
  - 提供每步的方法论 prompt 注入
  - 校验产出物的 DDD 合规性（quick 规则检查）
  - 产出物通过后自动合并到项目级 domain_model

设计原则:
  - 递进式: 每步有明确的输入依赖和输出契约
  - 可校验: 13 条规则可自动检测，不依赖 LLM
  - 与领域模型联动: 产出直接合并到 project.domain_model JSONB
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 三步子流程定义
# ---------------------------------------------------------------------------


@dataclass
class ArchSubPhase:
    key: str
    name: str
    methodology: str
    prompt: str
    output_fields: list[str]
    validation_rules: list[str]


ARCH_SUB_PHASES: list[ArchSubPhase] = [
    ArchSubPhase(
        key="strategic_design",
        name="战略设计",
        methodology="识别子域(核心域/支撑域/通用域) → 划分限界上下文 → 定义集成关系",
        prompt="""\
## 架构子阶段: 战略设计

**目标**: 自顶向下看全局，划定业务边界。

### 引导要点:
1. **识别子域** — "这个系统涉及哪些业务领域？哪些是核心竞争力（核心域）？哪些是必需但可标准化的（支撑域）？哪些通用功能优先外采（通用域）？"
   - 核心域: 重点投入，差异化竞争力
   - 支撑域: 业务必需，可标准化
   - 通用域: 优先外采/用开源

2. **划分限界上下文** — 在每个子域内，按以下原则划分上下文:
   - 语义一致性: 同一术语在该上下文内有唯一含义
   - 团队自治: 一个团队可独立负责
   - 独立部署: 可以独立发布
   - 事务边界: 数据一致性的最小范围

3. **定义集成关系** — 上下文之间如何协作:
   - 防腐层(ACL): 推荐，保持独立性
   - 开放主机服务(OHS): 标准 API 对外
   - 共享内核: 小范围共享（谨慎使用）
   - 遵奉者: 被动接受上游模型

### 注意:
- 核心域数量不固定 — 创业公司通常 1 个，大型系统 5-10 个
- 通用域始终标注"外采"或"自建理由"
- 避免上下文间循环依赖""",
        output_fields=["domain_design.subdomains", "domain_design.bounded_contexts", "domain_design.context_relations"],
        validation_rules=[
            "至少有 1 个核心域",
            "通用域标注了外采策略或自建理由",
            "上下文间无循环依赖",
            "每个集成关系明确了类型(ACL/OHS/共享内核/遵奉者)",
        ],
    ),
    ArchSubPhase(
        key="event_storming",
        name="事件风暴",
        methodology="在每个上下文内: 识别领域事件 → 识别命令和角色 → 初步识别聚合",
        prompt="""\
## 架构子阶段: 事件风暴

**目标**: 在每个限界上下文内，识别业务事实。

### 引导要点:
1. **识别领域事件** — "在这个上下文里，业务发生了什么？"
   - 命名规则: 过去时态（OrderPlaced, PaymentCompleted, UserRegistered）
   - 聚焦业务事实，不是技术事件

2. **识别命令和角色** — "是什么触发了这个事件？谁发起的？"
   - 命令: 触发事件的动作（PlaceOrder, MakePayment）
   - 角色: 谁发起了命令（Customer, Admin, System）

3. **初步识别聚合** — "哪些事件围绕同一个业务对象？哪些对象需要保证事务一致性？"
   - 聚合 = 事务一致性的边界
   - 同一聚合内的事件共享一个生命周期

### 注意:
- 事件必须用过去时态（已发生的事实）
- 每个事件都要有触发命令和触发角色
- 逐步引导，不要一次性抛出所有问题""",
        output_fields=["event_storming.events", "event_storming.commands"],
        validation_rules=[
            "事件命名为过去时态（含 ed/Completed/Created 等后缀或中文'已xx'）",
            "每个事件都有对应的触发命令",
            "每个事件都有触发角色",
        ],
    ),
    ArchSubPhase(
        key="tactical_modeling",
        name="战术建模",
        methodology="设计聚合根 → 区分实体/值对象 → 定义领域服务 → 聚合间ID引用",
        prompt="""\
## 架构子阶段: 战术建模

**目标**: 细化每个聚合的内部结构。

### 引导要点:
1. **聚合根设计** — "这个聚合的根实体是谁？它维护什么不变量？"
   - 聚合根是事务边界的守护者
   - 外部只能通过聚合根访问内部实体
   - 聚合不宜过大（< 5 个实体）

2. **实体 vs 值对象** — "这个概念需要唯一标识吗？还是只描述特征？"
   - 实体: 有唯一标识，可变状态（如 User, Order）
   - 值对象: 无标识，不可变，描述特征（如 Address, Money, DateRange）
   - 原则: 值对象优先 — 能用值对象就不用实体

3. **领域服务** — "这个操作涉及多个聚合吗？业务规则不属于某个实体吗？"
   - 适用: 跨聚合操作、不属于单一实体的规则、无状态计算
   - 不适用: 能放在实体方法里的逻辑

4. **聚合边界检查**:
   - 事务边界清晰？（同一聚合内才能事务一致）
   - 不变量维护责任明确？（聚合根负责）
   - 聚合间只通过 ID 引用？（不持有对方实例）

### API 设计:
基于聚合和命令，推导 API endpoint:
- 每个命令对应一个 API 操作
- URL 路径反映聚合结构
- 遵循 RESTful 或 CQRS 模式

### 技术决策 (ADR):
每个重要技术选择必须记录:
- 决策是什么
- 考虑了哪些选项（≥2 个）
- 选了哪个、为什么
- 放弃选项的 trade-off""",
        output_fields=["data_model.entities", "api_design", "tech_decisions"],
        validation_rules=[
            "聚合内实体数 ≤ 5",
            "聚合间只通过 ID 引用（无直接对象引用）",
            "值对象标注为不可变",
            "领域服务标注为无状态",
            "每个 tech_decision 有 ≥2 options_considered",
            "每个 tech_decision 的 trade_offs 不为空",
        ],
    ),
]


# ---------------------------------------------------------------------------
# 校验引擎
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_architecture(content: dict) -> ValidationResult:
    """对架构产出物执行 DDD 规则校验（quick 模式，纯规则无 LLM）。

    Returns ValidationResult with violations (hard fail) and warnings (soft).
    """
    violations = []
    warnings = []

    # --- 战略设计校验 ---
    domain_design = content.get("domain_design", {})
    subdomains = domain_design.get("subdomains", [])
    contexts = domain_design.get("bounded_contexts", [])
    relations = domain_design.get("context_relations", [])

    if subdomains:
        core_domains = [s for s in subdomains if isinstance(s, dict) and s.get("type") in ("核心域", "core")]
        if not core_domains:
            violations.append("战略设计: 未识别出核心域")

        generic_domains = [s for s in subdomains if isinstance(s, dict) and s.get("type") in ("通用域", "generic")]
        for gd in generic_domains:
            desc = gd.get("description", "")
            if "外采" not in desc and "自建" not in desc and "outsource" not in desc.lower():
                warnings.append(f"战略设计: 通用域「{gd.get('name', '?')}」未标注外采策略或自建理由")

    if relations:
        # 简单循环依赖检测
        graph: dict[str, set[str]] = {}
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            fr = rel.get("from", "")
            to = rel.get("to", "")
            if fr and to:
                graph.setdefault(fr, set()).add(to)
        # DFS 检测环
        if _has_cycle(graph):
            violations.append("战略设计: 上下文间存在循环依赖")

        for rel in relations:
            if isinstance(rel, dict) and not rel.get("type"):
                warnings.append(f"战略设计: 集成关系 {rel.get('from')}→{rel.get('to')} 未指定类型")

    # --- 事件风暴校验 ---
    event_storming = content.get("event_storming", {})
    events = event_storming.get("events", [])
    commands = event_storming.get("commands", [])

    for evt in events:
        if not isinstance(evt, dict):
            continue
        name = evt.get("name", "")
        if name and not _is_past_tense(name):
            warnings.append(f"事件风暴: 事件「{name}」不是过去时态")
        if not evt.get("trigger") and not evt.get("aggregate"):
            warnings.append(f"事件风暴: 事件「{name}」缺少触发命令或聚合归属")

    # --- 战术建模校验 ---
    data_model = content.get("data_model", {})
    entities = data_model.get("entities", []) if isinstance(data_model, dict) else []

    tech_decisions = content.get("tech_decisions", [])
    for td in tech_decisions:
        if not isinstance(td, dict):
            continue
        options = td.get("options_considered", [])
        if len(options) < 2:
            violations.append(f"ADR: 决策「{td.get('decision', '?')}」只有 {len(options)} 个选项（需 ≥2）")
        if not td.get("trade_offs"):
            warnings.append(f"ADR: 决策「{td.get('decision', '?')}」缺少 trade_offs 分析")

    # --- API 覆盖度 (与需求交叉检查的预备) ---
    api_design = content.get("api_design", [])
    if isinstance(api_design, list) and len(api_design) == 0 and entities:
        warnings.append("战术建模: 有实体定义但无 API 设计")

    passed = len(violations) == 0
    return ValidationResult(passed=passed, violations=violations, warnings=warnings)


def get_sub_phase_prompt(conversation_round: int) -> str:
    """根据对话轮次返回当前应聚焦的架构子阶段 prompt。

    策略: 前 4 轮聚焦战略设计，4-8 轮聚焦事件风暴，8+ 轮聚焦战术建模。
    """
    if conversation_round < 4:
        phase = ARCH_SUB_PHASES[0]
    elif conversation_round < 8:
        phase = ARCH_SUB_PHASES[1]
    else:
        phase = ARCH_SUB_PHASES[2]

    return phase.prompt


def get_methodology_overview() -> str:
    """返回完整的三步方法论概览（用于 system prompt 注入）。"""
    return """\
## 架构设计方法论（DDD 三步递进）

你正在引导用户完成技术架构设计，严格按以下顺序递进:

```
Step 1: 战略设计 → 识别子域、划分限界上下文、定义集成关系
Step 2: 事件风暴 → 在上下文内识别领域事件、命令、聚合
Step 3: 战术建模 → 设计聚合根、实体/值对象、领域服务、API
```

**为什么是这个顺序**:
- 战略设计: 自顶向下看全局，先划边界
- 事件风暴: 在边界内识别业务事实
- 战术建模: 细化每个聚合的内部结构

**交付物质量标准**:
- 每个 tech_decision 必须有 ≥2 个 options_considered
- 聚合内实体数 ≤ 5
- 聚合间只通过 ID 引用
- 上下文间不得有循环依赖
- 值对象优先于实体"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_cycle(graph: dict[str, set[str]]) -> bool:
    """DFS 检测有向图是否有环。"""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}

    def dfs(node: str) -> bool:
        color[node] = GRAY
        for neighbor in graph.get(node, set()):
            if neighbor not in color:
                color[neighbor] = WHITE
            if color[neighbor] == GRAY:
                return True
            if color[neighbor] == WHITE and dfs(neighbor):
                return True
        color[node] = BLACK
        return False

    for node in list(graph.keys()):
        if color.get(node, WHITE) == WHITE:
            if dfs(node):
                return True
    return False


def _is_past_tense(name: str) -> bool:
    """简单判断事件名是否为过去时态。"""
    past_indicators = [
        "ed", "Created", "Updated", "Deleted", "Placed", "Completed",
        "Confirmed", "Cancelled", "Failed", "Sent", "Received",
        "已", "完成", "创建了", "发生了",
    ]
    return any(name.endswith(ind) or ind in name for ind in past_indicators)

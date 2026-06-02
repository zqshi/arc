# 执行计划：Skill 集成 + 质量体系升级

> 创建: 2026-06-02  
> 基于: RFC-001 双架构审计 + 5 个 Skill 分析  
> 目标: 将 Arc 从"一个 LLM + 固定 prompt"升级为"方法论驱动 + 门禁保障 + 后验闭环"的执行引擎

---

## 一、Skill 适配性评估

| Skill | 适配度 | 对应 Arc 阶段 | 核心价值 | 改造成本 |
|-------|--------|-------------|---------|---------|
| **decision-thinking-toolkit** | ⭐⭐⭐⭐⭐ | 需求澄清 (Clarification) | 替代死板的 6 层静态追问；提供第一性原理/价值评估/苏格拉底三套组合工具 | 中 |
| **ddd-toolkit** | ⭐⭐⭐⭐⭐ | 技术架构 (Architecture) | 替代当前"直接输出 JSON"模式；提供战略设计→事件风暴→战术建模的严格流程 + 自动校验 | 中 |
| **analysis-to-prd** | ⭐⭐⭐⭐ | 需求澄清 → 产出物生成 | **输入充分性校验机制** — 正是 Arc 当前的死代码 `INPUT_SUFFICIENCY_PROMPT` 该做的事 | 低 |
| **oss-evaluator** | ⭐⭐⭐ | 技术架构 (tech_decisions) | 当架构阶段涉及技术选型时，自动检索评估开源方案 | 低 |
| **prd-gen** | ⭐⭐ | 需求澄清产出物 | 模板结构和"输入覆盖度评估"理念有参考价值，但 Ezone 绑定不适用 | 仅参考 |

### 决策：集成 3 个，参考 2 个

- **直接集成改造**: decision-thinking-toolkit, ddd-toolkit, analysis-to-prd (充分性校验逻辑)
- **选择性集成**: oss-evaluator (作为架构阶段的可选工具)
- **仅参考设计**: prd-gen (模板结构 + 覆盖度预测机制)

---

## 二、各阶段质量诊断与改造方案

### 2.1 需求澄清阶段 — 重构

#### 当前问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | `INPUT_SUFFICIENCY_PROMPT` 死代码，从未执行 | P0 |
| 2 | `SOCRATIC_LAYERS` 是写死的列表，不区分需求类型 | P1 |
| 3 | 不做假设挑战、不做方向质疑 | P1 |
| 4 | Gate 只检查字段存在，不验证逻辑一致性 | P2 |

#### 改造方案：集成 decision-thinking-toolkit

**设计思路**: 将 decision-thinking 的三套工具作为澄清阶段的**子策略**，根据需求类型自动路由：

```python
class ClarificationStrategy:
    """需求澄清策略路由器 — 基于 decision-thinking-toolkit 改造"""
    
    ROUTE_RULES = {
        "new_domain": "first_principles",       # 全新领域/方向不明 → 第一性原理
        "feature_request": "value_assessment",   # 明确功能请求 → 产品价值评估
        "optimization": "socratic",             # 已有方案待验证 → 苏格拉底追问
        "unclear": "sufficiency_then_route",    # 信息不足 → 先充分性检测再路由
    }
```

**具体集成点**:

| 子策略 | 来源 | 在 Arc 中的触发条件 | 输出 |
|--------|------|-------------------|------|
| 充分性检测 | analysis-to-prd Step 2 | **每次用户消息后自动执行** | sufficient=true → 进入深度策略；false → 追问 |
| 第一性原理 | decision-thinking 工具 1 | 需求方向不明 / 战略转型类 | 重新定义的问题 + 多候选路径 |
| 产品价值评估 | decision-thinking 工具 2 | 有明确功能方向，需判断值不值 | 六维评分 + 决策建议 |
| 苏格拉底追问 | decision-thinking 工具 3 | 有方案需要验证 / 假设拷问 | 命题状态 + 风险清单 |

**新增门禁**:

```python
# 需求澄清阶段的前置门禁（替代死代码 INPUT_SUFFICIENCY_PROMPT）
SUFFICIENCY_GATE = {
    "required_signals": [
        {"name": "target_users", "check": "能回答'谁在用这个功能'"},
        {"name": "core_problem", "check": "能回答'用户遇到了什么痛点'"},
        {"name": "feature_direction", "check": "能回答'大致要做什么'"},
    ],
    "policy": "all_must_clear_before_generation",
}

# 需求产出物的后验门禁（新增交叉一致性）
REQUIREMENT_POST_GATE = {
    "structural": PHASE_REQUIRED_FIELDS["clarification"],  # 现有
    "consistency": [
        "user_stories 是否覆盖所有 target_users",
        "acceptance_criteria 是否覆盖所有 user_stories",
        "boundaries.in_scope 是否与 user_stories 对齐",
        "risk_assessment 是否回应了 assumptions 中低置信度的假设",
    ],
}
```

---

### 2.2 交互设计阶段 — 增强

#### 当前问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | Prompt 只说"设计交互方案"，无方法论引导 | P1 |
| 2 | 不验证 wireframe 是否覆盖所有用户场景 | P1 |
| 3 | 没有可用性启发式检查 | P2 |

#### 改造方案

**方法论注入** (无需外部 skill，内建):

```python
UI_DESIGN_METHODOLOGY = """
## 设计方法论（递进执行）

1. **用户旅程映射** — 基于需求规格中的 user_scenarios，绘制完整的用户旅程
2. **信息架构** — 基于旅程节点，定义页面层级和导航结构
3. **线框设计** — 逐页面产出 wireframe，每个 wireframe 必须标注对应的 user_story ID
4. **交互规则** — 状态转换、异常处理、空状态、加载状态
5. **可用性自检** — 对照 Nielsen 10 启发式原则自检
"""
```

**新增门禁**:

```python
UI_DESIGN_POST_GATE = {
    "structural": PHASE_REQUIRED_FIELDS["ui_design"],  # 现有
    "coverage": [
        "每个 user_scenario 是否有对应 wireframe page",
        "每个 wireframe 是否标注了对应的 user_story ID",
    ],
    "heuristic_check": [
        "系统状态可见性",
        "用户控制与自由",
        "一致性与标准",
        "错误预防",
        "容错性",
    ],
}
```

---

### 2.3 技术架构阶段 — 重构

#### 当前问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | 直接让 AI 输出 JSON，无设计过程 | P0 |
| 2 | ADR 不验证是否真的对比了多方案 | P1 |
| 3 | event_storming 结构有但未引导执行 | P1 |
| 4 | 不做实体关系一致性检查 | P2 |

#### 改造方案：集成 ddd-toolkit

**设计思路**: 将 ddd-toolkit 的三步流程嵌入架构阶段，作为强制子步骤：

```python
ARCHITECTURE_SUB_PHASES = [
    {
        "step": "strategic_design",
        "name": "战略设计",
        "methodology": "识别子域(核心域/支撑域/通用域) → 划分限界上下文 → 定义集成关系",
        "validation": "validate_strategy",  # ddd-toolkit 自动校验
        "output_fields": ["domain_design.subdomains", "domain_design.bounded_contexts", "domain_design.context_relations"],
    },
    {
        "step": "event_storming",
        "name": "事件风暴",
        "methodology": "在每个上下文内：识别领域事件(过去时态) → 识别命令和角色 → 初步识别聚合",
        "validation": "validate_event_storming",
        "output_fields": ["event_storming.events", "event_storming.commands"],
    },
    {
        "step": "tactical_modeling",
        "name": "战术建模",
        "methodology": "设计聚合根(事务边界) → 区分实体/值对象 → 定义领域服务 → 聚合间ID引用",
        "validation": "validate_modeling",
        "output_fields": ["data_model.entities", "api_design", "tech_decisions"],
    },
]
```

**ddd-toolkit 校验规则内嵌** (从 skill 提取):

```python
DDD_VALIDATION_RULES = {
    "strategic": [
        "核心域数量与业务规模匹配（小系统1个，大系统5-10个）",
        "通用域标注了'优先外采'或'自建理由'",
        "无循环依赖（上下文间）",
        "集成关系明确（ACL/OHS/共享内核/遵奉者）",
    ],
    "event_storming": [
        "事件命名为过去时态",
        "每个事件都有触发命令和触发角色",
        "聚合边界不超过5个实体",
    ],
    "tactical": [
        "聚合根维护不变量",
        "聚合间只通过ID引用",
        "值对象不可变",
        "领域服务无状态",
    ],
}
```

**新增门禁**:

```python
ARCHITECTURE_POST_GATE = {
    "structural": PHASE_REQUIRED_FIELDS["architecture"],  # 现有
    "ddd_validation": DDD_VALIDATION_RULES,  # 新增
    "adr_quality": [
        "每个 tech_decision 必须有 ≥2 options_considered",
        "每个 decision 的 reason 必须引用具体 constraint 或 requirement",
        "trade_offs 不得为空",
    ],
    "coverage": [
        "api_design 的 endpoint 数量 ≥ user_stories 数量",
        "data_model.entities 与 domain_design.bounded_contexts 对齐",
    ],
}
```

**技术选型场景**: 集成 oss-evaluator

当 `tech_decisions` 中涉及外部依赖选择时，自动触发：

```python
async def evaluate_tech_choice(decision: dict) -> dict:
    """当 tech_decision 涉及外部库/框架选型时，调用 oss-evaluator 逻辑"""
    if not _involves_external_dependency(decision):
        return decision
    
    # P0 业务匹配度 → P1 商用合规性 → P2 社区维护 → P3 技术质量 → P4 部署可行性
    evaluation = await _run_oss_evaluation(decision["options_considered"])
    decision["evaluation_evidence"] = evaluation
    return decision
```

---

### 2.4 开发实现阶段 — 补全

#### 当前问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | Pipeline 模式无工具执行（能力倒挂） | P0 |
| 2 | 无 TDD 引导 | P1 |
| 3 | 无代码审查反馈循环 | P1 |

#### 改造方案

```python
DEVELOPMENT_METHODOLOGY = """
## 开发方法论

1. **任务拆分** — 将 implementation_plan 拆为可独立验证的增量步骤
2. **TDD 循环** — 每步：先写失败测试 → 最小实现 → 重构
3. **验证闭环** — 每步完成后执行测试，确认 pass
4. **代码审查** — 最终产出前自审：DDD分层/命名/职责单一
"""

DEVELOPMENT_POST_GATE = {
    "structural": ["execution_log", "code_changes", "test_results"],
    "executable_checks": [
        "test_results 中无 FAIL 状态",
        "code_changes 覆盖了 implementation_plan 的所有步骤",
    ],
}
```

---

### 2.5 测试验证阶段 — 补全

#### 当前问题

| # | 问题 | 严重度 |
|---|------|--------|
| 1 | 不逐条对照 AC | P0 |
| 2 | 纯文本自述，不可审计 | P1 |

#### 改造方案

```python
TESTING_POST_GATE = {
    "structural": ["criteria_verification", "issues_found", "coverage_summary"],
    "ac_coverage": {
        "rule": "requirements.acceptance_criteria 中每个 AC-N 必须在 criteria_verification 中有对应条目",
        "check": "len(unmatched_acs) == 0",
    },
    "evidence_required": [
        "每个 pass 状态的 criteria 必须有 evidence 字段（测试命令输出/截图描述）",
    ],
}
```

---

### 2.6 经验沉淀阶段 — 增强

#### 当前状态: 基本完善，增加假设验证回环

```python
EXTRACTION_POST_GATE = {
    "structural": ["problem", "solution", "decisions"],
    "assumption_validation": [
        "requirements.assumptions 中的每个假设在 experience.assumptions_validated 中有对应条目",
        "每个假设标注 was_correct + lesson",
    ],
}
```

---

## 三、统一质量保障体系架构

```
┌────────────────────────────────────────────────────────────┐
│                    QualityAssurance                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │ Sufficiency  │  │   Gate       │  │ CrossCheck     │   │
│  │   Check      │  │ (per-phase)  │  │ (cross-phase)  │   │
│  │              │  │              │  │                │   │
│  │ 信息够不够？  │  │ 产出物合格？  │  │ 上下游一致？   │   │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘   │
│         │                  │                   │            │
│    PRE-GATE           POST-GATE          CROSS-GATE        │
│  (生成产出物前)     (确认产出物时)      (阶段切换时)        │
│                                                             │
│  触发时机:          触发时机:           触发时机:            │
│  - 每轮 AI 回复后   - 用户点确认时      - 进入下一阶段时     │
│  - 判断是否该        - 自动提取产出物后  - 全链路一致性       │
│    停止追问                                                 │
└────────────────────────────────────────────────────────────┘
```

### 交叉一致性检查矩阵

| 上游产出 | 下游产出 | 检查规则 |
|---------|---------|---------|
| requirement_spec.user_stories | ui_design.wireframes | 每个 story 有对应 wireframe |
| requirement_spec.user_stories | architecture.api_design | 每个 story 有对应 API |
| requirement_spec.acceptance_criteria | testing.criteria_verification | 逐条 check-off |
| requirement_spec.boundaries.constraints | architecture.tech_decisions | 每个约束被决策回应 |
| architecture.data_model.entities | domain_model.aggregates | 实体 ↔ 聚合对齐 |
| architecture.implementation_plan | development.code_changes | 每个 step 有对应 change |
| requirement_spec.assumptions | extraction.assumptions_validated | 假设回环验证 |

---

## 四、执行排期

### Phase 1: 基础修复 (1-2 个版本)

| # | 工作项 | 优先级 | 预估 |
|---|--------|--------|------|
| 1 | **激活充分性检测** — 将 `INPUT_SUFFICIENCY_PROMPT` 从死代码变为实际调用，集成 analysis-to-prd 的 Step 2 三项检测逻辑 | P0 | 2h |
| 2 | **Pipeline 接入 ToolAwareLoop** — 解决能力倒挂 | P0 | 4h |
| 3 | **统一 Gate 调用点** — conversation 模式也在自动提取产出物后触发 gate 评审 | P0 | 3h |
| 4 | 增强 gate 评审 — 加入 ADR 多方案验证 + AC 覆盖度检查 | P1 | 3h |

### Phase 2: 方法论注入 (2-3 个版本)

| # | 工作项 | 优先级 | 预估 |
|---|--------|--------|------|
| 5 | **集成 decision-thinking 到需求澄清** — 实现策略路由器 + 三套子策略的 prompt 模板 | P0 | 6h |
| 6 | **集成 ddd-toolkit 到架构阶段** — 三步子流程 + 校验规则 | P0 | 6h |
| 7 | UI 设计方法论注入 — 用户旅程 → 信息架构 → wireframe 递进 | P1 | 3h |
| 8 | 测试阶段 AC 逐条 check-off 机制 | P1 | 3h |

### Phase 3: 交叉验证 (1-2 个版本)

| # | 工作项 | 优先级 | 预估 |
|---|--------|--------|------|
| 9 | 实现 CrossCheck 引擎 — 跨阶段一致性验证 | P1 | 6h |
| 10 | 集成 oss-evaluator 到架构阶段 tech_decisions | P2 | 3h |
| 11 | 假设回环验证 — extraction 阶段回查 clarification 阶段的 assumptions | P2 | 2h |

### Phase 4: 引擎统一 (与 RFC-001 合并)

| # | 工作项 | 优先级 | 预估 |
|---|--------|--------|------|
| 12 | 合并双执行路径为 UnifiedEngine | P0 | 8h |
| 13 | ProcessController 配置化 | P1 | 4h |
| 14 | 前端 UI 自适应（阶梯/纯聊天统一组件） | P1 | 6h |

---

## 五、Skill 改造规格

### 5.1 decision-thinking → `ClarificationStrategyService`

**改造要点**:
- 去掉文件系统操作（不创建本地 .md 文件）
- 三套工具改为 prompt 注入策略（不依赖外部脚本）
- 路由逻辑内嵌到 `build_system_prompt()` 中，根据需求类型动态切换
- 保留逐章节引导的对话设计模式（不一次性抛出全模板）

**代码位置**: `backend/src/arc/application/execution/clarification_strategy.py` (新建)

### 5.2 ddd-toolkit → `ArchitectureMethodologyService`

**改造要点**:
- 去掉 PlantUML/脚本生成（产出直接进入 `domain_model` JSONB）
- 三步子流程映射为架构阶段的 3 个 sub-step marker
- 校验规则内嵌为 `DDD_VALIDATION_RULES` dict
- 保留"quick 规则检查 + deep LLM 分析"双模式 gate

**代码位置**: `backend/src/arc/application/execution/architecture_methodology.py` (新建)

### 5.3 analysis-to-prd → `SufficiencyGate`

**改造要点**:
- 只提取 Step 2 的三项充分性检测逻辑
- 改为每轮对话后自动执行（非一次性检测）
- 检测结果作为 metadata 附加在 conversation message 上
- sufficient=true 时在 AI 回复中注入"可以开始生成产出物了"的信号

**代码位置**: `backend/src/arc/application/execution/sufficiency_gate.py` (新建)

### 5.4 oss-evaluator → `TechSelectionTool`

**改造要点**:
- 作为 `ToolRegistry` 的可选工具注册
- 在架构阶段 prompt 中告知 AI："当你需要评估外部依赖时，使用 evaluate_oss 工具"
- 五维评估逻辑 (P0-P4) 内嵌为 tool handler
- 依赖 web search 能力（当前 ToolRegistry 不支持，需新增）

**代码位置**: `backend/src/arc/application/execution/tools.py` 中新增 `evaluate_oss` tool

---

## 六、质量指标（改造前后对比）

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 需求充分性自动检测 | ❌ (死代码) | ✅ 每轮对话后执行 |
| 澄清策略种类 | 1 (静态 Socratic) | 4 (充分性 + 第一性原理 + 价值评估 + 苏格拉底) |
| 架构设计有方法论引导 | ❌ | ✅ 战略设计 → 事件风暴 → 战术建模 |
| DDD 校验规则 | 0 | 13 条 (战略4 + 事件3 + 战术4 + ADR2) |
| 交叉一致性检查 | 0 | 7 对 |
| AC ↔ 测试逐条对照 | ❌ | ✅ |
| Pipeline 工具执行能力 | ❌ | ✅ |
| Conversation 模式门禁 | ❌ | ✅ |
| 技术选型有评估证据 | ❌ | ✅ (oss-evaluator) |
| 假设验证回环 | ❌ | ✅ (clarification → extraction) |

# RFC-001: 统一执行引擎 — 消除 Pipeline/Conversation 双架构

> 状态: Draft  
> 作者: Arc Team  
> 创建: 2026-06-02  
> 关联: backlog 技术债务

---

## 1. 问题陈述

### 1.1 双架构现状

当前系统存在两条独立的执行路径：

| 维度 | Pipeline 模式 | Conversation 模式 |
|------|--------------|------------------|
| 入口 service | `ConversationService` | `ConversationExecutionService` + `ExecutionEngine` |
| 对话拓扑 | N 个 conversation (per-phase) | 1 个 unified conversation |
| Prompt 构建 | `_build_system_prompt()` (phase-specific) | `PromptBuilder.build_system_prompt()` |
| AI 执行 | `AgentLoop` (text-only, 60K/180s) | `AgentLoop` OR `ToolAwareLoop` (120K/300s) |
| 产出物触发 | 用户手动 `generate_artifact` | `ArtifactExtractor` 自动提取 |
| 质量门禁 | `evaluate_gate()` 结构检查 + LLM 评审 | ❌ 无 |
| 工具执行 | ❌ 不支持 | ✅ 文件读写/命令执行/沙盒 |
| 编排 (multi-agent) | ❌ 不支持 | ✅ `OrchestrationService` |
| 漂移检测 | ❌ 不支持 | ✅ `DriftDetector` |
| 死循环检测 | ❌ 不支持 | ✅ `ErrorLoopDetector` |
| 经验注入 | ✅ 语义检索 + 格式化 | ✅ `MemoryScorer` 五维打分 |
| Autopilot | ❌ 不支持 | ✅ 多轮自动推进 + checkpoint |

### 1.2 核心矛盾

**选了"更严格的质量管控"（pipeline），反而得到了"更弱的 AI 执行能力"。**

用户面临一个反直觉的选择：
- 要质量保障 → 选 pipeline → 但 AI 只能输出文本，不能真正执行
- 要执行能力 → 选 conversation → 但没有阶段门禁

这不是设计权衡，是重复实现导致的能力残缺。

### 1.3 代码冗余

- `ConversationService._build_llm_messages()` vs `PromptBuilder.build_llm_messages()` — 同一职责两套实现
- WebSocket handler 的 `purpose == "unified"` 分支 — 本应是同一 service 的不同配置
- pipeline 的 `PHASE_SYSTEM_PROMPTS` vs conversation 的 `CONVERSATION_MODE_SYSTEM_PROMPT` — 同一信息的两种注入方式

---

## 2. 现有各环节能力审计

### 2.1 需求澄清 (Clarification)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 主动追问 | ⚠️ 半成品 | `SOCRATIC_LAYERS` 6 层追问框架存在，但只在 pipeline 的 `ConversationService._build_clarification_prompt()` 中使用；conversation 模式完全不用 |
| 充分性判断 | ❌ 死代码 | `INPUT_SUFFICIENCY_PROMPT` 已定义但**从未被调用**——没有任何代码引用它 |
| 方法论 | ⚠️ 静态 | 6 层 Socratic 追问是写死的列表，不根据领域类型、需求复杂度动态调整 |
| 门禁 | ✅ 有 | `PHASE_REQUIRED_FIELDS["clarification"]` 检查 5 个必填字段 + LLM 质量评审 |
| 后验 | ⚠️ 不够 | gate 只验证"字段是否存在"和"LLM打分≥7"，不验证逻辑一致性（如用户故事是否覆盖所有场景） |

**关键缺失**:
1. 没有"信息充分性"的主动判断——AI 不知道什么时候该停止追问
2. 没有对需求自身一致性的验证（场景 vs 验收标准是否对齐）
3. Conversation 模式完全跳过了 Socratic 层级递进

### 2.2 交互设计 (UI Design)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 主动澄清 | ❌ | 无主动追问机制，直接基于需求规格生成 |
| 方法论 | ⚠️ 浅 | prompt 只说"设计交互方案"，未引导用户旅程地图、信息架构、可用性启发式等方法 |
| 门禁 | ✅ | 必须有 flow_diagram + wireframes + component_specs |
| 后验 | ❌ | 不验证 wireframe 是否覆盖了需求中的所有场景，不做可用性审查 |

**关键缺失**:
1. 没有要求产出覆盖所有用户故事
2. 没有可用性启发式评估（Nielsen 10 原则之类）
3. wireframe 是 HTML 字符串，无法自动验证交互逻辑完整性

### 2.3 技术架构 (Architecture)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 主动澄清 | ❌ | 不追问技术约束/团队能力/运维成本 |
| 方法论 | ⚠️ 有结构无深度 | 输出了 DDD 三元组 (subdomain/context/aggregate) + event storming + ADR，但 prompt 没有引导 trade-off 分析 |
| 门禁 | ✅ | 必须有 architecture_overview + data_model + api_design + tech_decisions |
| 后验 | ⚠️ 弱 | gate 检查字段存在 + LLM 打分，但不做：实体关系一致性检查、API 与 story 覆盖度、非功能需求可行性验证 |

**关键缺失**:
1. `tech_decisions` 要求了 options_considered + trade_offs，但 gate 不验证是否真的做了多方案对比
2. 不检查 API 设计是否覆盖了所有用户故事
3. 不做 data_model ↔ domain_design 的一致性交叉验证

### 2.4 开发实现 (Development)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 工具执行 | ⚠️ 分裂 | Pipeline 模式通过 `AgentSessionManager` 启动外部 Agent（仅记录 session），不在对话流中；Conversation 模式在对话流中直接执行 |
| 漂移检测 | 仅 Conversation 模式 | Pipeline 模式的 agent session 是"发射后不管"，无漂移检测 |
| 方法论 | ❌ 缺失 | 没有 TDD 引导、没有增量实现策略、没有代码审查循环 |
| 门禁 | ⚠️ 弱 | 只检查 execution_log + code_changes + test_results 字段存在 |
| 后验 | ❌ | 不验证测试是否通过、不跑 linter、不做 code review |

**关键缺失**:
1. 开发质量完全依赖外部 Agent 的自主判断，系统无验证
2. Pipeline 模式的 Agent 执行结果不自动回流到 conversation
3. 没有"代码 → 测试 → 修复"的 feedback loop 编排

### 2.5 测试验证 (Testing)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 自动化测试 | ❌ | 纯文本对话，不执行测试 |
| 验收标准覆盖 | ⚠️ | prompt 注入了 acceptance_criteria，但不主动检查逐条覆盖 |
| 方法论 | ❌ | 没有测试策略引导（等价类/边界值/场景驱动） |
| 门禁 | ✅ | 必须有 criteria_verification + issues_found + coverage_summary |
| 后验 | ❌ | gate 不验证 criteria_verification 是否覆盖了所有 AC |

**关键缺失**:
1. 不自动对照 clarification 阶段的 acceptance_criteria 逐条 check-off
2. 不执行实际测试代码
3. 测试报告是自述式的，不可审计

### 2.6 部署上线 (Deployment)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 自动部署 | ❌ | 纯文本 |
| 健康检查 | ❌ | 字段定义了但不执行 |
| 门禁 | ⚠️ | 只检查 deploy_log + health_check_result |
| 回滚计划 | ⚠️ | 字段存在但不验证可操作性 |

### 2.7 经验沉淀 (Extraction)

| 能力 | 实现状态 | 问题 |
|------|---------|------|
| 自动提取 | ✅ | `ExperienceService.extract_from_todo()` 在 autopilot 完成时触发 |
| 结构化 | ✅ | problem/solution/decisions/pitfalls 结构完善 |
| 复用回注 | ✅ | `MemoryScorer` 五维打分 + 语义检索回注到 prompt |
| 门禁 | ✅ | 必须有 problem + solution + decisions |

---

## 3. 统一方案设计

### 3.1 架构目标

```
┌─────────────────────────────────────────────────────────┐
│                 UnifiedExecutionEngine                    │
│  ┌─────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ToolAware│  │ AgentLoop│  │ OrchestrationService   │ │
│  │  Loop   │  │(text-only)│  │(multi-agent dispatch)  │ │
│  └────┬────┘  └─────┬────┘  └───────────┬───────────┘ │
│       └──────────────┴───────────────────┘              │
│                         ▲                                │
│              ┌──────────┴──────────┐                    │
│              │  ProcessController   │ ← 核心新增         │
│              │  (约束策略 × 能力)    │                    │
│              └──────────┬──────────┘                    │
│                         │                                │
│  ┌─────────┐  ┌────────┴───────┐  ┌─────────────────┐ │
│  │DriftDet.│  │ QualityGate    │  │ ArtifactExtractor│ │
│  │ErrorLoop│  │ (per-deliverable)│  │ (auto+manual)   │ │
│  └─────────┘  └────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
                         ▲
         ┌───────────────┼───────────────┐
         │               │               │
    strict (阶梯UI)  moderate       free (纯聊天UI)
    强制排序+gate    推荐顺序       无phase概念
    显式confirm     宽松gate       自动提取
```

### 3.2 ProcessController — 核心抽象

```python
class ProcessConstraint(StrEnum):
    STRICT = "strict"       # = 当前 pipeline
    MODERATE = "moderate"   # 新增：有推荐顺序但不卡死
    FREE = "free"           # = 当前 conversation

@dataclass
class PhaseConfig:
    """每个交付物类型的过程约束配置"""
    deliverable_type: str
    gate_enabled: bool          # 是否启用门禁
    gate_strictness: str        # strict / moderate / relaxed
    auto_extract: bool          # AI 回复后自动提取 or 手动触发
    requires_explicit_confirm: bool  # 用户必须手动确认
    tool_execution: bool        # 是否允许工具执行
    clarification_strategy: str # socratic / sufficiency_check / free
    post_validation: list[str]  # 后验规则列表
```

### 3.3 统一 Prompt 体系

现有 pipeline 的 `PHASE_SYSTEM_PROMPTS` 和 conversation 的 `CONVERSATION_MODE_SYSTEM_PROMPT` 合并为：

```
BaseSystemPrompt (项目上下文 + 经验 + DDD)
  + DeliverableDirective (当前应产出什么 + schema)
  + MethodologyHint (当前阶段推荐的方法论)
  + ClarificationPolicy (何时追问、追问策略)
  + PriorArtifacts (已确认的前置产出物)
```

不再区分"pipeline prompt"和"conversation prompt"——差异只在 `DeliverableDirective` 的范围：
- strict 模式：一次只给一个 deliverable 的指令
- free 模式：给全部未完成 deliverable 的指令

### 3.4 增强的质量保障体系

#### 3.4.1 前验：主动澄清 (Proactive Clarification)

```python
class ClarificationStrategy:
    """信息充分性判断 + 主动追问"""
    
    async def check_sufficiency(self, context: dict) -> SufficiencyResult:
        """调用 LLM 评估当前信息是否足够推进"""
        # 使用现有的 INPUT_SUFFICIENCY_PROMPT（目前是死代码，激活它）
        ...
    
    async def suggest_questions(self, current_layer: int) -> list[str]:
        """基于 Socratic 层级 + 领域上下文动态生成追问"""
        ...
```

每个阶段的澄清策略：

| 阶段 | 澄清策略 | 触发条件 |
|------|---------|---------|
| 需求 | Socratic 6 层递进 + 充分性检测 | 每轮对话后自动评估 |
| 设计 | 场景覆盖度检测 | 用户故事 vs wireframe 交叉检查 |
| 架构 | 约束完整性检测 | 非功能需求/团队能力/运维约束 |
| 开发 | 阻塞点识别 | 工具执行报错时 |
| 测试 | AC 覆盖度缺口 | criteria_verification vs acceptance_criteria |

#### 3.4.2 门禁：per-deliverable 质量门

```python
class QualityGate:
    """统一的质量门禁 — 结构检查 + 语义验证 + 交叉一致性"""
    
    async def evaluate(self, deliverable: Artifact, context: GateContext) -> GateResult:
        # 1. 结构检查 — PHASE_REQUIRED_FIELDS（现有）
        # 2. LLM 语义质量评审（现有）
        # 3. 交叉一致性验证（新增）
        #    - requirement → architecture: API 覆盖所有 user story？
        #    - architecture → testing: 所有实体都有对应测试？
        #    - clarification → testing: AC 逐条 check-off
        ...
```

#### 3.4.3 后验：交叉一致性检查

| 检查 | 逻辑 |
|------|------|
| story ↔ API 覆盖度 | 每个 user_story 是否都有对应的 API endpoint |
| AC ↔ test 覆盖度 | 每个 acceptance_criteria 是否在 criteria_verification 中有 pass/fail |
| entity ↔ domain_model | data_model.entities 是否与 domain_model.aggregates 对齐 |
| wireframe ↔ story | 每个 wireframe page 是否对应了至少一个 user scenario |
| tech_decisions ↔ constraints | 每个决策是否回应了至少一个 boundary constraint |

### 3.5 方法论升级（每阶段）

| 阶段 | 当前方法 | 目标方法 |
|------|---------|---------|
| 需求澄清 | Socratic 6 层 (静态列表) | **动态 Socratic + 充分性检测 + 假设挑战** — 根据需求类型(新功能/优化/修复)调整追问深度；信息充分时自动终止 |
| 交互设计 | 直接生成 wireframe | **用户旅程优先 + 信息架构 + 可用性启发式** — 先出 user journey map，再推导 IA，最后具象化 wireframe；gate 做 Nielsen 启发式检查 |
| 技术架构 | 直接出 DDD + API | **约束驱动设计 + ADR 强制对比 + event storming** — 先列 constraints，再做 C4 Model 分层，ADR 要求≥2 options |
| 开发实现 | 纯文本/外部 Agent | **TDD 循环 + 增量提交 + 自动测试** — 工具执行内联，red-green-refactor 编排 |
| 测试验证 | 文本描述覆盖度 | **AC 逐条对照 + 自动执行 + 覆盖度量** — 真跑测试，报告 pass/fail 证据 |
| 经验沉淀 | 全量提取 | **决策归因 + 假设验证 + 可复用性评估** — 标注哪些假设被验证/推翻 |

---

## 4. 迁移策略

### Phase 1: 统一底层（无用户感知变化）
- 合并 `ConversationService.generate_response_stream()` 和 `ExecutionEngine.generate_response_stream()`
- Pipeline 模式接入 `ToolAwareLoop`（解决能力倒挂）
- 激活 `INPUT_SUFFICIENCY_PROMPT`（当前死代码）

### Phase 2: 统一 Prompt 体系
- 合并 `PHASE_SYSTEM_PROMPTS` 和 `CONVERSATION_MODE_SYSTEM_PROMPT` 为模块化 Prompt
- Pipeline 模式的 per-phase conversation 改为 unified conversation + phase marker

### Phase 3: ProcessController
- 引入 `ProcessConstraint` 配置
- 前端根据配置决定展示"阶梯 UI"还是"纯聊天 UI"
- 删除 `ExecutionMode` 枚举，改为 `process_constraint` 配置

### Phase 4: 方法论升级
- 实现 per-deliverable 的 clarification strategy
- 实现交叉一致性验证
- 增强 gate 评审深度

---

## 5. 指标

| 指标 | 当前 | 目标 |
|------|------|------|
| 后端执行路径数 | 2 (ConversationService + ExecutionEngine) | 1 |
| Pipeline 工具执行能力 | ❌ | ✅ |
| 需求充分性自动判断 | ❌ (死代码) | ✅ |
| AC ↔ 测试逐条覆盖验证 | ❌ | ✅ |
| 交叉一致性检查 | 0 个 | 5 个 |

---

## 6. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| 数据迁移 — per-phase conversation → unified | 已有数据丢失上下文 | Phase 2 做 conversation 合并脚本 |
| Pipeline 用户习惯变更 | 阶梯 UI 用户适应成本 | 保留阶梯 UI 但底层统一 |
| Gate 评审延迟增加 | 交叉验证增加 LLM 调用 | 增量验证（只验证新增 deliverable vs 已有上下文） |

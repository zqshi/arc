# RFC-002: Skill 集成 + 质量体系升级 — 实施报告

> 状态: ✅ **已实施**  
> 创建: 2026-06-02  
> 完成: 2026-06-02  
> 基于: RFC-001 双架构审计 + 9 个外部 Skill 评估  
> 目标: 将 Arc 从"一个 LLM + 固定 prompt"升级为"方法论驱动 + 门禁保障 + 后验闭环"的执行引擎

---

## 一、外部 Skill 评估与决策

### 第一批 (本地 zip)

| Skill | 适配度 | 决策 | 对应阶段 | 实施状态 |
|-------|--------|------|---------|---------|
| **decision-thinking-toolkit** v1.0 | ⭐⭐⭐⭐⭐ | ✅ 集成 | 需求澄清 | ✅ 已实施 |
| **ddd-toolkit** v0.3.1 | ⭐⭐⭐⭐⭐ | ✅ 集成 | 技术架构 | ✅ 已实施 |
| **analysis-to-prd** v1.1.0 | ⭐⭐⭐⭐ | ✅ 提取核心 | 充分性检测 | ✅ 已实施 |
| **oss-evaluator** v0.1.0 | ⭐⭐⭐ | ⏳ 待集成 | 技术选型 | 规格已定，待 web search 工具支持 |
| **prd-gen** v0.7.5 | ⭐⭐ | 📖 参考 | — | 模板结构影响了 Gate 设计理念 |

### 第二批 (GitHub)

| Skill | 适配度 | 决策 | 对应阶段 | 实施状态 |
|-------|--------|------|---------|---------|
| **obra/superpowers** | ⭐⭐⭐⭐⭐ | ✅ 集成 | 开发 + 测试 | ✅ 已实施 |
| **anthropics/frontend-design** | ⭐⭐⭐⭐ | ✅ 集成 | UI 设计 | ✅ 已实施 |
| **ui-ux-pro-max** | ⭐⭐⭐ | ✅ 部分集成 | UI 设计 Gate | ✅ 检查清单 + 校验规则已实施 |
| **microsoft/playwright-mcp** | ⭐⭐⭐⭐ | ✅ 沙盒集成 | 验证全阶段 | ✅ 已实施 |

---

## 二、实施交付物清单

### 新建模块 (7 个文件, ~1700 行)

| 文件 | 来源 Skill | 职责 |
|------|-----------|------|
| `sufficiency_gate.py` | analysis-to-prd Step 2 | 三项必要信号检测 (target_users / core_problem / feature_direction) |
| `clarification_strategy.py` | decision-thinking-toolkit | 4 策略自动路由 + prompt 模板 (第一性原理/价值评估/苏格拉底/充分性优先) |
| `architecture_methodology.py` | ddd-toolkit v0.3.1 | DDD 三步流程 + 13 条校验规则 + 循环依赖检测 |
| `ui_design_methodology.py` | frontend-design + ui-ux-pro-max | 设计四步递进 + Nielsen 10 启发式 + 反模式 + 产出物校验 |
| `dev_test_methodology.py` | obra/superpowers | TDD 循环 + 增量实现 + AC 逐条验证 + 证据要求 |
| `playwright_sandbox.py` | playwright-mcp | 沙盒浏览器验证 (截图/健康检查/E2E断言) |

### 改造模块 (4 个文件)

| 文件 | 改造内容 |
|------|---------|
| `prompt_builder.py` | 全阶段方法论动态注入 + 充分性提示 |
| `prompts.py` | 系统 prompt 模板新增 `{methodology_section}` + `{sufficiency_hint}` |
| `gate.py` | 方法论校验 + 交叉一致性检查 (5 阶段全覆盖) |
| `pipeline/service.py` | confirm_phase 增加 prior_artifacts 交叉检查 + 架构确认后自动合并领域模型 |
| `artifact_extractor.py` | conversation 模式产出物提取后自动执行 gate 校验 |

---

## 三、全阶段方法论覆盖 (最终实现)

### 3.1 需求澄清 (Clarification)

**方法论**: decision-thinking-toolkit 三套工具  
**实现**: `clarification_strategy.py`

| 策略 | 触发条件 | 递进阶段 |
|------|---------|---------|
| 充分性优先 | 信息不足 (描述 < 20 字 + 对话 < 2 轮) | 收集三项基本信号 |
| 第一性原理 | 新业务/方向不明/竞品跟随 | 原始问题→追问根因→底层约束→重定义→重构方案→挑战假设 |
| 产品价值评估 | 明确功能请求 | 六维拆解: 用户→场景→痛点→现有方案→核心方法→预期价值 |
| 苏格拉底追问 | 已有方案待验证/优化 | 概念澄清→假设探查→证据审视→替代观点→后果检验→反诘 |

**门禁**: 
- 前验: `SufficiencyGate` 三项信号 (target_users/core_problem/feature_direction)
- 后验: user_stories 覆盖 target_users / AC 数量 ≥ P0 stories

### 3.2 交互设计 (UI Design)

**方法论**: anthropics/frontend-design + ui-ux-pro-max  
**实现**: `ui_design_methodology.py`

| 步骤 | 对话轮次 | 内容 |
|------|---------|------|
| 设计思维 | 0-2 | 目的/调性/约束/差异化 |
| 信息架构 | 2-4 | 用户旅程 + 页面层级 + 信息优先级 |
| 线框设计 | 4-8 | 逐页面产出 + story ID 标注 + 状态定义 |
| 可用性自检 | 8+ | Nielsen 10 启发式 + 反模式 checklist |

**门禁**:
- wireframe 关联 user_story ID
- 空状态/加载态定义
- 预交付 8 项 checklist

**验证** (Playwright 沙盒):
- `render_and_screenshot(html)` → prototype 可渲染性验证

### 3.3 技术架构 (Architecture)

**方法论**: ddd-toolkit v0.3.1  
**实现**: `architecture_methodology.py`

| 子阶段 | 对话轮次 | 产出 | 校验规则 |
|--------|---------|------|---------|
| 战略设计 | 0-4 | subdomains + bounded_contexts + relations | 有核心域/通用域标注外采/无循环依赖/集成类型明确 |
| 事件风暴 | 4-8 | events + commands | 过去时态/有触发命令/有触发角色 |
| 战术建模 | 8+ | entities + api_design + tech_decisions | 聚合≤5实体/ID引用/ADR≥2选项/trade_offs非空 |

**门禁**: 13 条规则 (3 violations 阻断 + 10 warnings 记录)  
**交叉检查**: API 端点数 ≥ P0 user_stories 数  
**领域模型**: gate 通过后自动合并到 `project.domain_model`

### 3.4 开发实现 (Development)

**方法论**: obra/superpowers (TDD + verification-before-completion)  
**实现**: `dev_test_methodology.py`

| 阶段 | 内容 |
|------|------|
| 任务拆分 | implementation_plan → 原子步骤 (2-5min) |
| TDD 循环 | RED → GREEN → REFACTOR → COMMIT |
| 增量推进 | 逐步骤 + 持续验证 |
| 收尾验证 | 全量测试 + lint + 覆盖度 |

**门禁**: test_results 无 FAIL / code_changes 非空  
**调试方法论**: 复现→定位→根因→验证 (4 阶段)

### 3.5 测试验证 (Testing)

**方法论**: obra/superpowers (verification-before-completion)  
**实现**: `dev_test_methodology.py`

| 原则 | 实现 |
|------|------|
| AC 逐条验证 | 每个 AC-N 必须有 pass/fail + evidence |
| 证据驱动 | pass 必须有 stdout/断言日志/截图证据 |
| P0 100% 覆盖 | P0 AC 数量 ≤ criteria_verification 数量 |

**门禁**: criteria_verification 非空 / pass 有证据 / P0 覆盖度  
**交叉检查**: AC ID 在 criteria_verification 中逐条匹配  
**验证** (Playwright 沙盒): `run_assertions(url, [{type, text}])` → E2E 自动化

### 3.6 部署上线 (Deployment)

**验证** (Playwright 沙盒): `verify_url_health(url)` → HTTP status + body preview

### 3.7 经验沉淀 (Extraction)

**增强**: 假设回环验证 — `requirements.assumptions` 中每个假设在 experience.assumptions_validated 中有对应条目

---

## 四、质量保障架构 (已实现)

```
┌────────────────────────────────────────────────────────────┐
│                    QualityAssurance                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│  │ Sufficiency  │  │ Methodology  │  │ CrossCheck     │   │
│  │   Gate       │  │ Validation   │  │ (cross-phase)  │   │
│  │              │  │              │  │                │   │
│  │ 信息够不够？  │  │ 方法论合规？  │  │ 上下游一致？   │   │
│  └──────┬───────┘  └──────┬───────┘  └───────┬────────┘   │
│         │                  │                   │            │
│    PRE-GATE           POST-GATE          CROSS-GATE        │
│  (生成产出物前)     (确认产出物时)      (阶段切换时)        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Playwright Sandbox                        │  │
│  │  render_and_screenshot | verify_url_health |          │  │
│  │  run_assertions                                       │  │
│  │  独立子进程 | headless | timeout 30s | 仅返回结果     │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 交叉一致性检查矩阵 (已实现)

| 检查点 | 上游 | 下游 | 实现位置 |
|--------|------|------|---------|
| story ↔ user 覆盖 | target_users | user_stories.role | `gate.py` _check_methodology |
| AC ↔ story P0 | user_stories (P0) | acceptance_criteria | `gate.py` _check_methodology |
| API ↔ story 覆盖 | user_stories (P0) | api_design | `gate.py` _check_cross_consistency |
| AC ↔ test 覆盖 | acceptance_criteria | criteria_verification | `gate.py` _check_cross_consistency |
| wireframe ↔ story | user_story | wireframes.story_id | `ui_design_methodology.py` validate |

---

## 五、领域模型持续演进闭环

```
需求迭代 N                    需求迭代 N+1
    │                              │
    ▼                              ▼
Architecture 产出物          PromptBuilder 注入最新 domain_model
    │                              ▲
    ▼                              │
Gate 通过                     project.domain_model (持续累积)
    │                              ▲
    ▼                              │
DomainModelExtractor ──────────────┘
  extract_and_merge()
  合并: subdomains + contexts + aggregates + events
```

**实现路径**:
1. `PipelineService.confirm_phase(ARCHITECTURE)` → `_merge_domain_model()`
2. `ArtifactExtractor.process_message()` → `_try_extract_domain_model()`
3. `PromptBuilder._build_project_context()` → `build_ddd_tdd_section(project.domain_model)`

---

## 六、质量指标 (改造前后对比)

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 方法论覆盖阶段数 | 0/7 | **7/7** |
| 需求充分性自动检测 | ❌ (死代码) | ✅ 三项信号检测 |
| 澄清策略种类 | 1 (静态列表) | **4** (动态路由) |
| UI 设计方法论 | 无 | **四步递进 + Nielsen 10** |
| DDD 校验规则 | 0 | **13 条** |
| 开发方法论 | 无 | **TDD + 增量实现** |
| 测试 AC 逐条对照 | ❌ | ✅ |
| 交叉一致性检查 | 0 对 | **5 对** |
| 浏览器自动验证 | ❌ | ✅ (Playwright 沙盒) |
| Conversation 模式门禁 | ❌ | ✅ (产出物提取后自动 gate) |
| 领域模型自动合并 | 手动触发 | ✅ gate 通过后自动 |
| 方法论校验维度 (gate) | 1 (结构检查) | **3** (结构 + 方法论 + 交叉) |

---

## 七、待办 (后续版本)

| # | 工作项 | 依赖 | 状态 |
|---|--------|------|------|
| 1 | oss-evaluator 完整集成 | ToolRegistry 支持 web search | ⏳ 待 web search tool |
| 2 | Playwright 前端集成 | 前端展示截图/验证结果 | ⏳ 待前端适配 |
| 3 | 充分性检测 LLM 调用版 (非轻量提示) | 成本评估 | ⏳ 待 A/B 测试 |
| 4 | RFC-001 引擎统一 | 本 RFC 稳定后 | ⏳ v4.0.0 |

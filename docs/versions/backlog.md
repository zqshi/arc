# Backlog — 后续版本规划

> 这是粗粒度的版本规划, 不是承诺。每个版本启动时再细化为 current.md。
> 最后更新: 2026-06-01

---

## 已完成版本

- [v0.1.0](v0.1.0-snapshot.md) · [v0.2.0](v0.2.0-snapshot.md) · [v0.3.0](v0.3.0-snapshot.md) · [v0.4.0](v0.4.0-snapshot.md) · [v0.5.0](v0.5.0-snapshot.md)
- [v1.0.0](v1.0.0-snapshot.md) · [v1.1.0](v1.1.0-snapshot.md) · [v1.2.0](v1.2.0-snapshot.md)
- [v2.0.0](v2.0.0-snapshot.md) · [v2.1.0](v2.1.0-snapshot.md) · [v2.2.0](v2.2.0-snapshot.md) · [v2.3.0](v2.3.0-snapshot.md) · [v2.4.0](v2.4.0-snapshot.md) · [v2.5.0](v2.5.0-snapshot.md) · [v2.6.0](v2.6.0-snapshot.md) · [v2.7.0](v2.7.0-snapshot.md) · [v2.8.0](v2.8.0-snapshot.md) · [v2.9.0](v2.9.0-snapshot.md) · [v3.0.0](v3.0.0-snapshot.md) · [v3.1.0](v3.1.0-snapshot.md) · [v3.2.0](v3.2.0-snapshot.md) · [v3.3.0](v3.3.0-snapshot.md) · [v3.4.0](v3.4.0-snapshot.md) · [v3.5.0](v3.5.0-snapshot.md) · [v3.6.0](v3.6.0-snapshot.md) · [v3.7.0](v3.7.0-snapshot.md) · [v3.8.0](v3.8.0-snapshot.md) · [v3.9.0 待规划]

---

## 技术债务 (可穿插在任何版本中)

| 工作项 | 优先级 | 来源 | 状态 |
|--------|--------|------|------|
| domain/organization 模块缺少测试 | P2 | v2.2.0 质量检测 6.6 | v2.9.0 T2 |
| application 层部分 service 缺少测试 (auth/artifact/agent_loop) | P2 | v2.2.0 质量检测 6.6 | pending |
| 前端测试体系建立 | P3 | v2.2.0 质量检测 6.6 | pending |
| planning_service.py ~557 行, 需拆分 | P1 | v2.2.0 质量检测 6.5 | ✅ v3.3.0 (557→487) |
| 值对象建模 — 12 个 dict 字段应显式建模 | P2 | v2.3.0 审计 | v3.0.0 关联 (ReviewFeedback/DomainModelSnapshot 值对象化) |
| 聚合边界重构 — service 跨聚合直接访问 repo | P2 | v2.3.0 审计 | pending (需 DI 完成后) |
| domain_model 无版本历史/无回滚能力 | P1 | v2.9.0 升级路径设计 | ✅ v3.0.0 |
| Validator 评审结果无闭环流程 | P1 | v2.9.0 升级路径设计 | ✅ v3.0.0 |
| Pipeline/Conversation 双架构冗余 | P0 | RFC-001 审计 | v4.0.0 |
| INPUT_SUFFICIENCY_PROMPT 死代码 | P0 | RFC-001 审计 | ✅ RFC-002 (sufficiency_gate.py) |
| Pipeline 无 tool-use 能力 (能力倒挂) | P0 | RFC-001 审计 | v4.0.0 Phase 1 |
| AC ↔ 测试无交叉一致性验证 | P1 | RFC-001 审计 | ✅ RFC-002 (gate.py _check_cross_consistency) |
| 全阶段无方法论引导 | P0 | RFC-002 审计 | ✅ RFC-002 (7/7 阶段覆盖) |
| Conversation 模式零门禁 | P0 | RFC-002 审计 | ✅ RFC-002 (artifact_extractor 补 gate) |
| UI 设计无质量标准 | P1 | RFC-002 审计 | ✅ RFC-002 (ui_design_methodology.py) |
| 开发阶段无 TDD 引导 | P1 | RFC-002 审计 | ✅ RFC-002 (dev_test_methodology.py) |
| oss-evaluator 技术选型评估 | P2 | RFC-002 规划 | ⏳ 待 web search tool |
| Playwright 前端验证结果展示 | P2 | RFC-002 规划 | ⏳ 待前端适配 |
| 前端 4 个组件超 500 行 | P2 | v2.3.0 质量检测 | v2.9.0 T4 |
| application 层循环依赖 (2 个环) | P1 | v2.3.0 质量检测 | v2.9.0 T1 (顶层已修复) |
| tool_loop 穿透 adapter 封装 | P2 | v2.3.0 遗留 | v2.4.0 T4+T5 |
| 扫描状态纯内存不持久化 | P1 | v2.3.0 用户反馈 | v2.4.0 T1 |
| 项目硬删除无恢复能力 | P1 | v2.3.0 用户反馈 | v2.4.0 T2 |

---

## ~~v3.0.0 — 领域模型升级基础设施 (Phase 1)~~ ✅ 已完成

> [v3.0.0-snapshot.md](v3.0.0-snapshot.md)

---

## ~~v3.1.0 — 领域模型影响分析 (Phase 2)~~ ✅ 已完成

> [v3.1.0-snapshot.md](v3.1.0-snapshot.md)

---

## ~~v3.2.0 — 领域模型升级执行机制 (Phase 3)~~ ✅ 已完成

> [v3.2.0-snapshot.md](v3.2.0-snapshot.md)

---

## v4.0.0 — 统一执行引擎 (RFC-001)

> **RFC**: [docs/rfcs/RFC-001-unified-execution-engine.md](../rfcs/RFC-001-unified-execution-engine.md)  
> **目标**: 消除 Pipeline/Conversation 双架构，统一为单引擎 + 配置化约束策略  
> **预计**: 3 个 phase (Phase 4 方法论已由 RFC-002 提前完成)

### 核心问题

选了"更严格的质量管控"(pipeline)，反而得到了"更弱的AI执行能力"——两条路径从两端出发正在走向同一个中心，但各自能力残缺。

### Phase 规划

| Phase | 内容 | 关键交付 | 状态 |
|-------|------|---------|------|
| Phase 1 | 统一底层执行 | Pipeline 接入 ToolAwareLoop | ⏳ 待实施 |
| Phase 2 | 统一 Prompt 体系 | 模块化 prompt 替代双系统 prompt | ⏳ 待实施 |
| Phase 3 | ProcessController | `process_constraint` 配置替代 `execution_mode` 枚举 | ⏳ 待实施 |
| ~~Phase 4~~ | ~~方法论升级~~ | ~~每阶段方法论 + 交叉验证 + AC check-off~~ | ✅ **RFC-002 已完成** |

### 原始能力缺陷 — 修复状态

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | `INPUT_SUFFICIENCY_PROMPT` 死代码 | P0 | ✅ `sufficiency_gate.py` |
| 2 | Pipeline 模式无工具执行能力（能力倒挂） | P0 | ⏳ Phase 1 |
| 3 | AC ↔ 测试报告无逐条覆盖验证 | P1 | ✅ `gate.py` _check_cross_consistency |
| 4 | 交互设计不检查覆盖度 | P1 | ✅ `ui_design_methodology.py` validate |
| 5 | 架构 ADR 不验证多方案对比 | P2 | ✅ `architecture_methodology.py` (≥2 options) |
| 6 | Conversation 模式无门禁 | P1 | ✅ `artifact_extractor.py` 补 gate |
| 7 | Socratic 追问静态列表 | P2 | ✅ `clarification_strategy.py` (4策略路由) |

---

## ~~v3.10.0 — Skill 集成 + 质量体系升级 (RFC-002)~~ ✅ 已完成

> **RFC**: [docs/rfcs/RFC-002-skill-integration-quality-plan.md](../rfcs/RFC-002-skill-integration-quality-plan.md)  
> **实施日期**: 2026-06-02  
> **交付**: 7 个新模块 (~1700 行) + 4 个改造模块

### 集成的外部 Skill (9 个评估, 7 个集成)

| Skill | 来源 | 集成位置 |
|-------|------|---------|
| decision-thinking-toolkit | 本地 zip | `clarification_strategy.py` |
| ddd-toolkit | 本地 zip | `architecture_methodology.py` |
| analysis-to-prd | 本地 zip | `sufficiency_gate.py` |
| obra/superpowers | GitHub | `dev_test_methodology.py` |
| anthropics/frontend-design | GitHub | `ui_design_methodology.py` |
| ui-ux-pro-max | GitHub | `ui_design_methodology.py` (校验规则) |
| playwright-mcp | GitHub | `playwright_sandbox.py` |

---

## 跨版本约束

这些约束跨越多个版本, 任何版本的开发都必须遵守:

1. **架构约束**: DDD分层不可破坏 — domain层不依赖infrastructure
2. **数据兼容**: 数据库schema变更必须有migration, 不允许破坏性变更
3. **API兼容**: 已发布的API端点不改签名, 新增字段用optional
4. **经验数据**: 经验表结构的变更必须考虑存量数据迁移
5. **二代预留**: 功能设计需考虑"第二代: AI驱动, 人审批"的演化方向(见arc_system_essence.md)

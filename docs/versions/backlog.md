# Backlog — 后续版本规划

> 这是粗粒度的版本规划, 不是承诺。每个版本启动时再细化为 current.md。
> 最后更新: 2026-06-24

---

## 已完成版本

- [v0.1.0](v0.1.0-snapshot.md) · [v0.2.0](v0.2.0-snapshot.md) · [v0.3.0](v0.3.0-snapshot.md) · [v0.4.0](v0.4.0-snapshot.md) · [v0.5.0](v0.5.0-snapshot.md)
- [v1.0.0](v1.0.0-snapshot.md) · [v1.1.0](v1.1.0-snapshot.md) · [v1.2.0](v1.2.0-snapshot.md)
- [v2.0.0](v2.0.0-snapshot.md) · [v2.1.0](v2.1.0-snapshot.md) · [v2.2.0](v2.2.0-snapshot.md) · [v2.3.0](v2.3.0-snapshot.md) · [v2.4.0](v2.4.0-snapshot.md) · [v2.5.0](v2.5.0-snapshot.md) · [v2.6.0](v2.6.0-snapshot.md) · [v2.7.0](v2.7.0-snapshot.md) · [v2.8.0](v2.8.0-snapshot.md) · [v2.9.0](v2.9.0-snapshot.md) · [v3.0.0](v3.0.0-snapshot.md) · [v3.1.0](v3.1.0-snapshot.md) · [v3.2.0](v3.2.0-snapshot.md) · [v3.3.0](v3.3.0-snapshot.md) · [v3.4.0](v3.4.0-snapshot.md) · [v3.5.0](v3.5.0-snapshot.md) · [v3.6.0](v3.6.0-snapshot.md) · [v3.7.0](v3.7.0-snapshot.md) · [v3.8.0](v3.8.0-snapshot.md) · [v3.9.0](v3.9.0-snapshot.md) · [v3.10.0](v3.10.0-snapshot.md)
- [v4.0.0](v4.0.0-snapshot.md) · [v4.1.0](v4.1.0-snapshot.md) · [v4.2.0](v4.2.0-snapshot.md) · [v4.3.0](v4.3.0-snapshot.md) · [v4.4.0](v4.4.0-snapshot.md) · [v4.5.0](v4.5.0-snapshot.md) · [v4.6.0](v4.6.0-snapshot.md) · [v4.7.0](v4.7.0-snapshot.md) · [v4.8.0](v4.8.0-snapshot.md) · [v4.9.0](v4.9.0-snapshot.md) · [v5.0.0](v5.0.0-snapshot.md) · [v5.1.0](v5.1.0-snapshot.md) · [v5.2.0](v5.2.0-snapshot.md) · [v5.3.0](v5.3.0-snapshot.md) · [v5.4.0](v5.4.0-snapshot.md) · [v5.5.0](v5.5.0-snapshot.md) · [v5.6.0](v5.6.0-snapshot.md) · [v5.7.0](v5.7.0-snapshot.md) · [v5.8.0](v5.8.0-snapshot.md)

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
| Pipeline 无 tool-use 能力 (能力倒挂) | P0 | RFC-001 审计 | ✅ RFC-001 Phase 1 (ConversationService 接入 ToolAwareLoop) |
| AC ↔ 测试无交叉一致性验证 | P1 | RFC-001 审计 | ✅ RFC-002 (gate.py _check_cross_consistency) |
| 全阶段无方法论引导 | P0 | RFC-002 审计 | ✅ RFC-002 (7/7 阶段覆盖) |
| Conversation 模式零门禁 | P0 | RFC-002 审计 | ✅ RFC-002 (artifact_extractor 补 gate) |
| UI 设计无质量标准 | P1 | RFC-002 审计 | ✅ RFC-002 (ui_design_methodology.py) |
| 开发阶段无 TDD 引导 | P1 | RFC-002 审计 | ✅ RFC-002 (dev_test_methodology.py) |
| oss-evaluator 技术选型评估 | P2 | RFC-002 规划 | ⏳ 待 web search tool |
| Playwright 前端验证结果展示 | P2 | RFC-002 规划 | ⏳ 待前端适配 |
| 前端 4 个组件超 500 行 | P2 | v2.3.0 质量检测 | v2.9.0 T4 |
| application 层循环依赖 (2 个环) | P1 | v2.3.0 质量检测 | v2.9.0 T1 (顶层已修复) |
| useProjectDetail.ts 超限 (510行) | P2 | v5.1.0 质量检测 | ✅ v5.2.0 T1 |
| v5.1.0 改动文件缺配套单元测试 (provider/service/strategy) | P2 | v5.1.0 质量检测 6.6 | ✅ v5.2.0 T2 |
| `tool_loop.py` 511 行 / `pipeline/service.py` 503 行 | P2 | v5.4.0 质量检测 6.5 | v5.6.0 拆分 (pipeline/service 在 v5.5.0 T5/T6 后必然超限需先拆) |
| `context/prompts.py` 504 行 (v5.5.0 触及) | P3 | v5.5.0 质量检测 6.5 | 已加例外注释；超 800 行必修 |
| MCP server (v5.5.0 T9/T12 deferred) | P2 | v5.5.0 决策 | ✅ v5.6.0 T18/T19 (原生 endpoint, 非 Higress) |
| `tool_loop.py` 511 行 / `pipeline/service.py` 503 行 / `prompts.py` 504 行 | P2 | v5.4/5.5 质量检测 6.5 | v5.7.0 拆分 |
| `execution/tools.py` 567 行 (v5.6.0 触及) | P3 | v5.6.0 质量检测 6.5 | 已加例外注释; 超 800 必修 |
| docker-compose Supabase 环境 | P2 | v5.6.0 T13 剩余 | 生产部署时补 |
| Higress MCP 网关接入 | P3 | v5.6.0 部署架构选项 | 待实际部署据官方文档配置 |
| MCP stdio transport | P3 | v5.6.0 仅 HTTP | Claude Desktop stdio 后续补 |
| 模板提取 LLM embed 自动生成 | P2 | v5.7.0 release hook 未生成 embedding | ✅ v5.8.0 T4 (extract_template 内自动生成) |
| `tool_loop.py`/`pipeline/service.py`/`prompts.py` 超 500 行 | P2 | v5.4-5.5 遗留 | ✅ v5.8.0 T1-T3 拆分 (全回归 500 内) |
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

## ~~v4.0.0 — 统一执行引擎 (RFC-001)~~ ✅ 已完成

> [v4.0.0-snapshot.md](v4.0.0-snapshot.md)

---

## ~~v3.10.0 — Skill 集成 + 质量体系升级 (RFC-002)~~ ✅ 已完成

> [v3.10.0-snapshot.md](v3.10.0-snapshot.md)

---

## v6.0.0 — 容器化构建 runtime + 原生客户端构建

> BINARY_APP 类型落地地基。激活 v5.9.0 框架的第二个项目类型。

- 实现 `DockerSandboxRuntime`（当前 `raise NotImplementedError`）+ 构建工具链容器镜像（node/rust/tauri/capacitor）
- `run_command` 容器内执行 + 跨平台编译编排
- `ProjectType.BINARY_APP` 构建链路（cargo tauri build / npx cap build 产出二进制）
- `BinaryArtifactDeployer`（产物落制品目录，不签名不分发）
- 验证: 原生客户端项目本地构建出 .dmg/.exe/.apk

---

## v6.1.0 — 签名/公证层（凭证可配置，非阻塞）

- 签名器抽象 + Apple codesign+notarize / Windows signtool / Android apksigner
- 凭证 Settings 配置项（必须同步 `.env.example`）：`APPLE_DEV_ID` / `APPLE_TEAM_ID` / `WIN_EV_CERT_PATH` / `WIN_EV_PASSWORD` / `PLAY_KEY_JSON`
- **未配 → graceful skip**（warning，不阻断构建）；配了 → 走签名流程
- 验证: 配凭证后包签名+notarize 通过

---

## v6.2.0 — 商店分发 + 制品分发层（凭证可配置）

- App Store Connect / Play Console / Tauri updater 上传器
- 二进制制品分发层（下载页 / 更新元数据）
- 未配凭证 → skip 商店上传，产物落制品仓可手动下载
- 验证: 配凭证后能上传商店

---

## 跨版本约束

这些约束跨越多个版本, 任何版本的开发都必须遵守:

1. **架构约束**: DDD分层不可破坏 — domain层不依赖infrastructure
2. **数据兼容**: 数据库schema变更必须有migration, 不允许破坏性变更
3. **API兼容**: 已发布的API端点不改签名, 新增字段用optional
4. **经验数据**: 经验表结构的变更必须考虑存量数据迁移
5. **二代预留**: 功能设计需考虑"第二代: AI驱动, 人审批"的演化方向(见arc_system_essence.md)

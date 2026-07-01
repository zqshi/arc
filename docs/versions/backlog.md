# Backlog — 后续版本规划

> 这是粗粒度的版本规划, 不是承诺。每个版本启动时再细化为 current.md。
> 最后更新: 2026-07-01 (v6.20 已归档: LLM 多厂商凭证管理 + 在线探活, 见 v6.20.0-snapshot.md, 全局默认走 env 渐进边界留 v6.21; v6.21 已激活: LLM 链路深化 + 技术债清理, 见 v6.21.0-current.md)

---

## 已完成版本

- [v0.1.0](v0.1.0-snapshot.md) · [v0.2.0](v0.2.0-snapshot.md) · [v0.3.0](v0.3.0-snapshot.md) · [v0.4.0](v0.4.0-snapshot.md) · [v0.5.0](v0.5.0-snapshot.md)
- [v1.0.0](v1.0.0-snapshot.md) · [v1.1.0](v1.1.0-snapshot.md) · [v1.2.0](v1.2.0-snapshot.md)
- [v2.0.0](v2.0.0-snapshot.md) · [v2.1.0](v2.1.0-snapshot.md) · [v2.2.0](v2.2.0-snapshot.md) · [v2.3.0](v2.3.0-snapshot.md) · [v2.4.0](v2.4.0-snapshot.md) · [v2.5.0](v2.5.0-snapshot.md) · [v2.6.0](v2.6.0-snapshot.md) · [v2.7.0](v2.7.0-snapshot.md) · [v2.8.0](v2.8.0-snapshot.md) · [v2.9.0](v2.9.0-snapshot.md) · [v3.0.0](v3.0.0-snapshot.md) · [v3.1.0](v3.1.0-snapshot.md) · [v3.2.0](v3.2.0-snapshot.md) · [v3.3.0](v3.3.0-snapshot.md) · [v3.4.0](v3.4.0-snapshot.md) · [v3.5.0](v3.5.0-snapshot.md) · [v3.6.0](v3.6.0-snapshot.md) · [v3.7.0](v3.7.0-snapshot.md) · [v3.8.0](v3.8.0-snapshot.md) · [v3.9.0](v3.9.0-snapshot.md) · [v3.10.0](v3.10.0-snapshot.md)
- [v4.0.0](v4.0.0-snapshot.md) · [v4.1.0](v4.1.0-snapshot.md) · [v4.2.0](v4.2.0-snapshot.md) · [v4.3.0](v4.3.0-snapshot.md) · [v4.4.0](v4.4.0-snapshot.md) · [v4.5.0](v4.5.0-snapshot.md) · [v4.6.0](v4.6.0-snapshot.md) · [v4.7.0](v4.7.0-snapshot.md) · [v4.8.0](v4.8.0-snapshot.md) · [v4.9.0](v4.9.0-snapshot.md) · [v5.0.0](v5.0.0-snapshot.md) · [v5.1.0](v5.1.0-snapshot.md) · [v5.2.0](v5.2.0-snapshot.md) · [v5.3.0](v5.3.0-snapshot.md) · [v5.4.0](v5.4.0-snapshot.md) · [v5.5.0](v5.5.0-snapshot.md) · [v5.6.0](v5.6.0-snapshot.md) · [v5.7.0](v5.7.0-snapshot.md) · [v5.8.0](v5.8.0-snapshot.md) · [v5.9.0](v5.9.0-snapshot.md) · [v5.10.0](v5.10.0-snapshot.md) · [v6.0.0](v6.0.0-snapshot.md) · [v6.1.0](v6.1.0-snapshot.md) · [v6.2.0](v6.2.0-snapshot.md) · [v6.3.0](v6.3.0-snapshot.md) · [v6.4.0](v6.4.0-snapshot.md) · [v6.5.0](v6.5.0-snapshot.md) · [v6.6.0](v6.6.0-snapshot.md) · [v6.7.0](v6.7.0-snapshot.md) · [v6.8.0](v6.8.0-snapshot.md) · [v6.9.0](v6.9.0-snapshot.md) · [v6.10.0](v6.10.0-snapshot.md) · [v6.11.0](v6.11.0-snapshot.md) · [v6.12.0](v6.12.0-snapshot.md) · [v6.13.0](v6.13.0-snapshot.md) · [v6.14.0](v6.14.0-snapshot.md) · [v6.15.0](v6.15.0-snapshot.md) · [v6.16.0](v6.16.0-snapshot.md) · [v6.18.0](v6.18.0-snapshot.md) · [v6.19.0](v6.19.0-snapshot.md) · [v6.20.0](v6.20.0-snapshot.md)

---

## 技术债务 (可穿插在任何版本中)

| 工作项 | 优先级 | 来源 | 状态 |
|--------|--------|------|------|
| domain/organization 模块缺少测试 | P2 | v2.2.0 质量检测 6.6 | ✅ 2026-06-29 核实: test_organization_service / test_organization_entity / test_organization_value_objects 均已存在 |
| application 层部分 service 缺少测试 (auth/artifact/agent_loop) | P2 | v2.2.0 质量检测 6.6 | ⚠️ 2026-06-29 核实过时: test_auth_service / test_artifact_service(+extractor/deployer/binary/gate 5 文件) / test_agent_loop 均已存在 (tests/unit/application 共 111 文件)。原"缺测试"描述不准; 改为评估覆盖度 |
| 前端测试体系建立 | P3 | v2.2.0 质量检测 6.6 | ✅ 2026-06-29 核实: frontend/src 共 17 个 .test.tsx/.ts (vitest 91 passed), 覆盖组件/hook/api client |
| planning_service.py ~557 行, 需拆分 | P1 | v2.2.0 质量检测 6.5 | ✅ v3.3.0 (557→487) |
| 值对象建模 — 12 个 dict 字段应显式建模 | P2 | v2.3.0 审计 | v3.0.0 关联 (ReviewFeedback/DomainModelSnapshot 值对象化) |
| 聚合边界重构 — service 跨聚合直接访问 repo | P2 | v2.3.0 审计 | ⚠️ 2026-06-29 核实仍存在: pipeline/hooks.py 直接 ProjectRepository(db)/ArtifactRepository(db); planning_experience.py 直接 ExperienceRepository(db)。pending (需 DI 重构), 真未做 |
| domain_model 无版本历史/无回滚能力 | P1 | v2.9.0 升级路径设计 | ✅ v3.0.0 |
| Validator 评审结果无闭环流程 | P1 | v2.9.0 升级路径设计 | ✅ v3.0.0 |
| Pipeline/Conversation 双架构冗余 | P0 | RFC-001 审计 | ✅ 2026-06-29 核实已消解: conversation/service.py docstring 明确"委托 ExecutionEngine, 与 ConversationExecutionService(unified) 委托同一引擎"; pipeline/service.py 无 AgentLoop/ToolAwareLoop 引用 (退化为阶段编排器: initialize/start_phase/confirm/gate, 不自跑 AI)。RFC-001 统一执行引擎目标达成, 双架构非冗余 (编排层 vs 执行层正交) |
| INPUT_SUFFICIENCY_PROMPT 死代码 (sufficiency_gate.py 在 v4.1.0/ef66656 已删回归) | P0 | RFC-001 审计 / v5.10 复核 | ✅ v6.0 #7: 接线为 requirement_spec 产出门禁(`execution/sufficiency_gate.py`), 不再零调用 |
| Pipeline 无 tool-use 能力 (能力倒挂) | P0 | RFC-001 审计 | ✅ RFC-001 Phase 1 (ConversationService 接入 ToolAwareLoop) |
| AC ↔ 测试无交叉一致性验证 | P1 | RFC-001 审计 | ✅ RFC-002 (gate.py _check_cross_consistency) |
| 全阶段无方法论引导 | P0 | RFC-002 审计 | ✅ RFC-002 (7/7 阶段覆盖) |
| Conversation 模式零门禁 | P0 | RFC-002 审计 | ✅ RFC-002 (artifact_extractor 补 gate) |
| UI 设计无质量标准 | P1 | RFC-002 审计 | ✅ RFC-002 (ui_design_methodology.py) |
| 开发阶段无 TDD 引导 | P1 | RFC-002 审计 | ✅ RFC-002 (dev_test_methodology.py) |
| oss-evaluator 技术选型评估 | P2 | RFC-002 规划 | ⏳ 2026-06-29 核实: oss-evaluator.skill 已建 (skill 层面就绪), "待 web search tool" 不再成立; 真未做的是评估工作本身 (待专项执行, 非工具缺失) |
| Playwright 前端验证结果展示 | P2 | RFC-002 规划 | ⏳ 待前端适配 |
| 前端 4 个组件超 500 行 | P2 | v2.3.0 质量检测 | ✅ 2026-06-29 核实: 无 .tsx 超 500 行 (全 <500), v2.9.0 T4 已拆 |
| application 层循环依赖 (2 个环) | P1 | v2.3.0 质量检测 | ✅ 2026-06-29 AST 扫环确认: 89 模块无环 (顶层已修复, 与 v2.9.0 T1 标注一致) |
| useProjectDetail.ts 超限 (510行) | P2 | v5.1.0 质量检测 | ✅ v5.2.0 T1 |
| v5.1.0 改动文件缺配套单元测试 (provider/service/strategy) | P2 | v5.1.0 质量检测 6.6 | ✅ v5.2.0 T2 |
| `tool_loop.py` 511 行 / `pipeline/service.py` 503 行 | P2 | v5.4.0 质量检测 6.5 | ✅ 2026-06-29 核实: pipeline/service.py 453 行 (<500); tool_loop.py 已不存在 (改名 execution/tools.py 419 行)。v5.8.0 T1-T3 拆分已落地 |
| `context/prompts.py` 504 行 (v5.5.0 触及) | P3 | v5.5.0 质量检测 6.5 | ✅ 2026-06-29 核实: 220 行 (<500, v5.8.0 拆分后已达标), 无需例外 |
| MCP server (v5.5.0 T9/T12 deferred) | P2 | v5.5.0 决策 | ✅ v5.6.0 T18/T19 (原生 endpoint, 非 Higress) |
| `tool_loop.py` 511 行 / `pipeline/service.py` 503 行 / `prompts.py` 504 行 | P2 | v5.4/5.5 质量检测 6.5 | ✅ 2026-06-29 核实: pipeline/service.py 453 / context/prompts.py 220, 均 <500 (与上行重复, v5.8.0 拆分已落地) |
| `execution/tools.py` 567 行 (v5.6.0 触及) | P3 | v5.6.0 质量检测 6.5 | ✅ 2026-06-29 核实: 419 行 (<500, v5.8.0 拆分后已达标) |
| docker-compose Supabase 环境 | P2 | v5.6.0 T13 剩余 | 生产部署时补 |
| Higress MCP 网关接入 | P3 | v5.6.0 部署架构选项 | 待实际部署据官方文档配置 |
| MCP stdio transport | P3 | v5.6.0 仅 HTTP | Claude Desktop stdio 后续补 |
| 模板提取 LLM embed 自动生成 | P2 | v5.7.0 release hook 未生成 embedding | ✅ v5.8.0 T4 (extract_template 内自动生成) |
| `tool_loop.py`/`pipeline/service.py`/`prompts.py` 超 500 行 | P2 | v5.4-5.5 遗留 | ✅ v5.8.0 T1-T3 拆分 (全回归 500 内) |
| tool_loop 穿透 adapter 封装 | P2 | v2.3.0 遗留 | ✅ 2026-06-29 核实: tool_loop.py 已不存在 (改名 execution/tools.py), 穿透问题随重构消解 |
| 扫描状态纯内存不持久化 | P1 | v2.3.0 用户反馈 | ✅ 2026-06-29 核实: scan_status 在 Project entity (entity.py:47) + repo persist (project.py:128/177) + route 读 DB (scanning.py:34), 非纯内存 |
| 项目硬删除无恢复能力 | P1 | v2.3.0 用户反馈 | ✅ 2026-06-29 核实: archive() + deleted_at (entity.py:74) + include_archived (repository.py:30), 软删可恢复 |
| `test_health` 全量连跑时序污染 | P2 | v5.10.0 质量检测 | ✅ v6.9.0 (test_health + `test_health_degraded_when_db_error` 分支覆盖 + conftest monkeypatch async_session_factory); 2026-06-29 复核: `pytest tests/integration -k "capability or health"` 合跑 21 passed |
| v6.0 波次2 — web 工具链镜像 | P2 | v6.0 遗留 | ✅ v6.12 T1 (arc/web-builder + BuildTarget.WEB 激活) |
| v6.0 波次3 — android capacitor 镜像 | P2 | v6.0 遗留 | ✅ v6.12 T2 (arc/android-builder JDK21+SDK+NDK + BuildTarget.CAPACITOR_APK 激活, apk smoke 通过) |
| tauri-builder smoke 手动验证 | P3 | v6.0 遗留 | CI 默认 skip; `make tauri-builder`(~10min) 后 `pytest -m slow` 跑; 完整 cargo tauri build 端到端留作手动 |
| v6.1 真实产物签名验证 | P2 | v6.1 遗留 | android apk 真实验证 ✅ v6.13 (apksigner sign/verify v2 通过); mac/win 待 Apple Developer ID 证书 / Windows runner |
| v6.1 notarytool --apple-id 用 team_id 兼用 | P3 | v6.1 遗留 | ✅ v6.13 T1 (SigningCredentials.apple_id, notarytool --apple-id 用 apple_id 非 team_id) |
| T4 project_member repository 接口(聚合边界未定) | P2 | v6.6 遗留 | 需先定 project_member 归 project 还是 organization 聚合, 再补 AbstractRepository+实现 |
| ProcessConfig 4 死字段 + create/update 双构造路径 | P1 | v6.15 审计 | ✅ v6.15 T4: 删 4 死字段, ProcessConfig 退化为 constraint 容器, from_execution_mode 单一映射点, 构造路径收敛 |
| 后端无模式守卫 | P1 | v6.15 审计 | ✅ v6.15 T5: pipeline 5 写操作接入 _require_pipeline_mode, FREE/MODERATE→409 mode_mismatch; 真相源 todo.project→project.process_constraint |
| strict 阈值双存 | P2 | v6.15 审计 | ✅ v6.16 (`gate.py:152` `if score < profile.score_threshold`, `get_profile(constraint)` 同源 GateProfile; `:87` 注释明记 v6.16 不再硬编码 score<7) |
| DELIVERABLES_BY_CONSTRAINT 死结构 + reorder 空操作 | P2 | v6.15 审计 | ✅ v6.16 (2026-06-29 核实: 全库 grep `DELIVERABLES_BY_CONSTRAINT` 零结果 = dict 已删; conversation_strategy 直接用 `REQUIRED_DELIVERABLES`, `_sync_tracker_required` 的 needs_reorder 为真实顺序同步非空操作) |
| 测试 DB 隔离缺陷 (capability 三文件合跑 409) | P2 | v6.15 质检发现 | ✅ v6.16 (`conftest.py:22-54` savepoint 事务隔离, `join_transaction_mode="create_savepoint"`, 被测代码 commit()/begin_nested() 退化为 savepoint, teardown rollback 外层事务, 不 truncate); 2026-06-29 复核 capability 合跑 21 passed |
| 历史数据 process_constraint 为 free | P1 | v6.15 T5 发现 | ✅ v6.15 T6: z18_backfill_process_constraint 回填 959 个 pipeline→free 为 strict, process_config 规整为 {constraint} 格式 |
| execution_mode deprecated 字段下线 | P2 | v6.15 审计 | ✅ v6.16 (2026-06-29 核实: `grep execution_mode backend/src/arc/domain/` 零匹配 = entity 字段已删; 前端 `grep execution_mode frontend/src/` 零结果 = UnifiedWorkspaceView 已不读; 后端仅余 3 处历史注释 `pipeline.py:40/57`+`conversations.py:62`, 真值已收敛到 process_constraint 单源) |
| infra 变量前缀设计债务 (root .env.example 混合 arc 配置 + compose infra, ARC_DB_PORT/ARC_WORKERS/ARC_PORT/ARC_*_IMAGE 用 ARC_ 前缀, cwd=root 读 .env 跑 arc 触发 pydantic forbid) | P2 | v6.18 归档质检 | pending |

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

## v6.0.0 — 容器化构建 runtime + 原生客户端构建（✅ 已完成 2026-06-24，见 [v6.0.0-snapshot.md](v6.0.0-snapshot.md)）

> BINARY_APP 类型落地地基。激活 v5.9.0 框架的第二个项目类型。
> 附加: prompt-upgrade-plan #7 sufficiency 接线 + ConstraintPolicy 死配置清理。

- ✅ **T1 done** DockerSandboxRuntime (groundwork, commit 292cc8d) — 真实容器执行 + RW 挂载产物持久化 + 超时/网络/内存限制 + 路径逃逸防护 (7 项真实 docker 测试通过)
- ✅ **T2 done(波次1)** 构建工具链容器镜像 — 自建 arc/tauri-builder:linux (rust+node+webkit2gtk+tauri-cli v2); 决策: 三目标按波次拆分, 架构层一次做对(BuildTarget 维度), 波次2/3 只填注册表
- ✅ **T3 done** run_command 容器内执行 + 镜像推导编排 (policy_resolver + build_images, runtime 零改)
- ✅ **T4 done** BINARY_APP 框架激活 — 六处注册点 + 前端 UI 选择器放开 (CreateProjectModal binary_app 卡片)
- ✅ **T5 done** BinaryArtifactDeployer — 二进制制品落 artifacts/ 不分发, 不要求 index.html
- ✅ **T6 done(波次1)** 容器内构建验证 — arc/tauri-builder:linux smoke 通过 (cargo 1.96/node v20.20.2/tauri-cli 2.11.3)
- ✅ **T7 done** #7 sufficiency 接线 — 产出前门禁方案(非A+B), 接 ArtifactService.confirm, 降级放行
- ✅ **T8 done** ConstraintPolicy 死配置清理 — 删 10/11 零引用字段(GateProfile 接管门禁), 仅留 methodology_depth
- ✅ **T9 done** 质量检测 — 6.1-6.5/6.7 必修全过, 6.6 测试覆盖全绿
- **遗留**: 波次2 web 镜像 / 波次3 android capacitor 镜像 (架构已就位, 独立推进); 注: #13 route_strategy 空参数清理属 v6.2

---

## v6.1.0 — 签名/公证层（✅ 已完成 2026-06-24，见 [v6.1.0-snapshot.md](v6.1.0-snapshot.md)）

> 凭证项目维度加密存储, 非阻塞 (未配 graceful skip)。

- ✅ **T1 done** Signer 抽象 + 凭证项目维度加密存储 (Fernet, domain 回调注入加解密, migration z12)
- ✅ **T2 done** Apple codesign+notarize 签名器
- ✅ **T3 done** Windows signtool 签名器
- ✅ **T4 done** Android apksigner 签名器 (app signing keystore, 非 Play 上传密钥)
- ✅ **T5 done** graceful skip 路由 (按产物平台 .app/.exe/.apk 检测, 非 build_target)
- ✅ **T6 done** mock 验证签名链路激活
- ✅ **T7 done** 质量检测 (cryptography 显式声明修 transitive)
- **遗留**: 真实产物签名验证待 v6.0 波次2/3 (mac/win/apk 构建链路)

---

## v6.2.0 — 商店分发 + 制品分发层（凭证可配置）✅ 已完成

→ [v6.2.0-snapshot.md](v6.2.0-snapshot.md)

---

## v6.3.0 — 项目治理规范传递（交付物初始化声明规范）✅ 已完成

→ [v6.3.0-snapshot.md](v6.3.0-snapshot.md)

---

## v6.4.0 — 债务清理 + prompt-upgrade P2（规则残留 LLM 化）✅ 已完成 2026-06-25

→ [v6.4.0-snapshot.md](v6.4.0-snapshot.md)

---

## v6.5.0 — execution 层拆分评估 + 测试补全 + config 核对 ✅ 已完成 2026-06-25

→ [v6.5.0-snapshot.md](v6.5.0-snapshot.md)

---

## v6.6.0 — 代码质量修复收尾 ✅ 已完成 2026-06-25

→ [v6.6.0-snapshot.md](v6.6.0-snapshot.md)

---

## v6.7.0 — 运行时入口补全（对话双轨统一+凭证API+skill热重载+charter门禁）✅ 已完成

→ [v6.7.0-snapshot.md](v6.7.0-snapshot.md)

---

## v6.8.0 — 能力注册表（Agent/Skill 声明管理+环节级配置）✅ 已完成

→ [v6.8.0-snapshot.md](v6.8.0-snapshot.md)

---

## v6.9.0 — test_health修复 + artifact显式建模 + 按类型编排 ✅ 已完成

→ [v6.9.0-snapshot.md](v6.9.0-snapshot.md)

---

## 跨版本约束

这些约束跨越多个版本, 任何版本的开发都必须遵守:

1. **架构约束**: DDD分层不可破坏 — domain层不依赖infrastructure
2. **数据兼容**: 数据库schema变更必须有migration, 不允许破坏性变更
3. **API兼容**: 已发布的API端点不改签名, 新增字段用optional
4. **经验数据**: 经验表结构的变更必须考虑存量数据迁移
5. **二代预留**: 功能设计需考虑"第二代: AI驱动, 人审批"的演化方向(见arc_system_essence.md)

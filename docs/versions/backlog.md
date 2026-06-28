# Backlog — 后续版本规划

> 这是粗粒度的版本规划, 不是承诺。每个版本启动时再细化为 current.md。
> 最后更新: 2026-06-28 (v6.15 过程约束依赖守卫治理归档; 下一版本方向待定)

---

## 已完成版本

- [v0.1.0](v0.1.0-snapshot.md) · [v0.2.0](v0.2.0-snapshot.md) · [v0.3.0](v0.3.0-snapshot.md) · [v0.4.0](v0.4.0-snapshot.md) · [v0.5.0](v0.5.0-snapshot.md)
- [v1.0.0](v1.0.0-snapshot.md) · [v1.1.0](v1.1.0-snapshot.md) · [v1.2.0](v1.2.0-snapshot.md)
- [v2.0.0](v2.0.0-snapshot.md) · [v2.1.0](v2.1.0-snapshot.md) · [v2.2.0](v2.2.0-snapshot.md) · [v2.3.0](v2.3.0-snapshot.md) · [v2.4.0](v2.4.0-snapshot.md) · [v2.5.0](v2.5.0-snapshot.md) · [v2.6.0](v2.6.0-snapshot.md) · [v2.7.0](v2.7.0-snapshot.md) · [v2.8.0](v2.8.0-snapshot.md) · [v2.9.0](v2.9.0-snapshot.md) · [v3.0.0](v3.0.0-snapshot.md) · [v3.1.0](v3.1.0-snapshot.md) · [v3.2.0](v3.2.0-snapshot.md) · [v3.3.0](v3.3.0-snapshot.md) · [v3.4.0](v3.4.0-snapshot.md) · [v3.5.0](v3.5.0-snapshot.md) · [v3.6.0](v3.6.0-snapshot.md) · [v3.7.0](v3.7.0-snapshot.md) · [v3.8.0](v3.8.0-snapshot.md) · [v3.9.0](v3.9.0-snapshot.md) · [v3.10.0](v3.10.0-snapshot.md)
- [v4.0.0](v4.0.0-snapshot.md) · [v4.1.0](v4.1.0-snapshot.md) · [v4.2.0](v4.2.0-snapshot.md) · [v4.3.0](v4.3.0-snapshot.md) · [v4.4.0](v4.4.0-snapshot.md) · [v4.5.0](v4.5.0-snapshot.md) · [v4.6.0](v4.6.0-snapshot.md) · [v4.7.0](v4.7.0-snapshot.md) · [v4.8.0](v4.8.0-snapshot.md) · [v4.9.0](v4.9.0-snapshot.md) · [v5.0.0](v5.0.0-snapshot.md) · [v5.1.0](v5.1.0-snapshot.md) · [v5.2.0](v5.2.0-snapshot.md) · [v5.3.0](v5.3.0-snapshot.md) · [v5.4.0](v5.4.0-snapshot.md) · [v5.5.0](v5.5.0-snapshot.md) · [v5.6.0](v5.6.0-snapshot.md) · [v5.7.0](v5.7.0-snapshot.md) · [v5.8.0](v5.8.0-snapshot.md) · [v5.9.0](v5.9.0-snapshot.md) · [v5.10.0](v5.10.0-snapshot.md) · [v6.0.0](v6.0.0-snapshot.md) · [v6.1.0](v6.1.0-snapshot.md) · [v6.2.0](v6.2.0-snapshot.md) · [v6.3.0](v6.3.0-snapshot.md) · [v6.4.0](v6.4.0-snapshot.md) · [v6.5.0](v6.5.0-snapshot.md) · [v6.6.0](v6.6.0-snapshot.md) · [v6.7.0](v6.7.0-snapshot.md) · [v6.8.0](v6.8.0-snapshot.md) · [v6.9.0](v6.9.0-snapshot.md) · [v6.10.0](v6.10.0-snapshot.md) · [v6.11.0](v6.11.0-snapshot.md) · [v6.12.0](v6.12.0-snapshot.md) · [v6.13.0](v6.13.0-snapshot.md) · [v6.14.0](v6.14.0-snapshot.md) · [v6.15.0](v6.15.0-snapshot.md)

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
| INPUT_SUFFICIENCY_PROMPT 死代码 (sufficiency_gate.py 在 v4.1.0/ef66656 已删回归) | P0 | RFC-001 审计 / v5.10 复核 | ✅ v6.0 #7: 接线为 requirement_spec 产出门禁(`execution/sufficiency_gate.py`), 不再零调用 |
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
| `test_health` 全量连跑时序污染 | P2 | v5.10.0 质检发现 | 🔴 待修复: `tests/integration/test_api.py::test_health` 断言 `status=="ok"`, 但 `/health` 端点用全局 `async_session_factory` 不走 `db_session` fixture, unit 全量跑完后连接池异常终止 → 返回 `degraded`; 单独跑 integration 或单独跑 test_health 均通过。非业务 bug, 是测试基础设施隔离缺陷 |
| v6.0 波次2 — web 工具链镜像 | P2 | v6.0 遗留 | ✅ v6.12 T1 (arc/web-builder + BuildTarget.WEB 激活) |
| v6.0 波次3 — android capacitor 镜像 | P2 | v6.0 遗留 | ✅ v6.12 T2 (arc/android-builder JDK21+SDK+NDK + BuildTarget.CAPACITOR_APK 激活, apk smoke 通过) |
| tauri-builder smoke 手动验证 | P3 | v6.0 遗留 | CI 默认 skip; `make tauri-builder`(~10min) 后 `pytest -m slow` 跑; 完整 cargo tauri build 端到端留作手动 |
| v6.1 真实产物签名验证 | P2 | v6.1 遗留 | android apk 真实验证 ✅ v6.13 (apksigner sign/verify v2 通过); mac/win 待 Apple Developer ID 证书 / Windows runner |
| v6.1 notarytool --apple-id 用 team_id 兼用 | P3 | v6.1 遗留 | ✅ v6.13 T1 (SigningCredentials.apple_id, notarytool --apple-id 用 apple_id 非 team_id) |
| T4 project_member repository 接口(聚合边界未定) | P2 | v6.6 遗留 | 需先定 project_member 归 project 还是 organization 聚合, 再补 AbstractRepository+实现 |
| ProcessConfig 4 死字段 + create/update 双构造路径 | P1 | v6.15 审计 | ✅ v6.15 T4: 删 4 死字段, ProcessConfig 退化为 constraint 容器, from_execution_mode 单一映射点, 构造路径收敛 |
| 后端无模式守卫 | P1 | v6.15 审计 | ✅ v6.15 T5: pipeline 5 写操作接入 _require_pipeline_mode, FREE/MODERATE→409 mode_mismatch; 真相源 todo.project→project.process_constraint |
| strict 阈值双存 | P2 | v6.15 审计 | 🔴 待修: `pipeline/gate.py:147` 硬编码 `score < 7` 绕过 GateProfile; 应改读 `get_profile(constraint).score_threshold` |
| DELIVERABLES_BY_CONSTRAINT 死结构 + reorder 空操作 | P2 | v6.15 审计 | 🔴 待修: 三档 key 指向同一列表, conversation_strategy reorder 实为空操作。建议删 dict 直接用 REQUIRED_DELIVERABLES |
| 测试 DB 隔离缺陷 (capability 三文件合跑 409) | P2 | v6.15 质检发现 | 🔴 待修: `conftest.py:39` db_session setup 阶段 commit() user 注入, teardown 只 rollback() 救不回已提交数据。真实共享 PG 跨 run 残留导致 test_capability_api 三文件合跑偶发 409 (清表后全绿)。同 v5.10 test_health 时序污染类。建议事务回滚隔离或测试前 truncate |
| 历史数据 process_constraint 为 free | P1 | v6.15 T5 发现 | ✅ v6.15 T6: z18_backfill_process_constraint 回填 959 个 pipeline→free 为 strict, process_config 规整为 {constraint} 格式 |
| execution_mode deprecated 字段下线 | P2 | v6.15 审计 | 🔴 待修: 前后端契约仍用 execution_mode (UnifiedWorkspaceView 读 todo.execution_mode==='pipeline'), 与 process_constraint 双源真值未收敛。需独立迁移: 前端改读 process_constraint + 后端删 entity.execution_mode |

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

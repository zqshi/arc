# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_v6.24 R5 端到端价值流验证 + BaaS provision 两个 P0 修复。_

### Fixed — BaaS provision 两个 P0 (R5 端到端验证暴露, 2026-07-02 修复)
- **P0-1 BaaS provision 在 pipeline 主路径不自动触发**: provision 只挂 conversation 模式 `artifact_extractor → try_provision_baas` 链, pipeline generate / domain-model/refresh 不接入 → 走 pipeline 永不 provision, baas-status 永远 false。修: `DomainModelService.provision_baas` 统一入口 (project.domain_model → apply_snapshot) + `refresh_domain_model` 提取后自动调 (try/except graceful) + `POST /projects/{id}/baas/provision` 手动端点。实测 pipeline→architecture generate→refresh→baas-status `provisioned=true`。
- **P0-2 provision 建表启用 RLS 但 0 policy → 非 superuser deny-all**: `DomainModelApplier` 返回 `policies=[]` + 表 `has_rls=True` → PostgreSQL 启用 RLS 无 policy = 默认拒绝 → Supabase anon/authenticated 不可读写 (dev superuser bypass 掩盖)。修: applier 按表生成默认 policy (有 user_id→行级隔离 `user_id = auth.uid()`, 无 user_id→authenticated 共享) + user_id 列 `DEFAULT auth.uid()`; `SchemaProvisioner` provision 时幂等预建 Supabase 约定 (authenticated/anon 角色 + auth.uid() 函数 — dev 兜底, Supabase 内置 IF NOT EXISTS 跳过, 禁 CREATE OR REPLACE 防污染)。实测 arc_xxx schema `pg_policies=4` (修复前 0)。

### Added — R5 方向验证
- **R5 端到端价值流验证 (推翻 blocked 误判)**: v6.23/backlog 标 "R5 blocked 需 PAT/S3/runner/证书" 是误判 — R5 只需真实 LLM + provision 链, 不依赖 R3/R4 构建凭证。实测智谱 glm-5-turbo (经 open.bigmodel.cn anthropic 兼容端点) 端到端跑通 ARCHITECTURE 产出 + domain_model 提取 + provision, 暴露上述两个 P0 (已修)。见 v6.24.0-current.md「R5 验证结论」。
- **provision 端点 + 测试**: `POST /projects/{id}/baas/provision` (3 集成测试) + `DomainModelApplier` 4 单测 (policy 生成/user_id DEFAULT/validate_rls 端到端)。CI 基线 ruff0 / pytest 2500 passed。

## [6.23.0] - 2026-07-01 — 投产检测后清单收口 (debt cleanup)

### Added — 投产检测后清单收口
- **C1 Cursor agent adapter 补实现**: 参照 claude_code CLI 子进程模式。核实 Cursor CLI 命令 `agent` + `-p` argv prompt (不支持 stdin) + text 输出 (无 JSON→每行 OBSERVATION) + 无 `--mcp-config` (mcp_servers 文本降级)。registry 零改动 (`implemented=True` 即注册)。6 集成测试。
- **G1 A 辅助模块 LLM 接 DB (9 处)**: experience×4/planning×3/project/artifact `create_resilient_adapter` (env) → `resolve_for_context` + `acquire_for_project` (DB 凭证)。helper `LLMProviderService.resolve_for_context` 统一入口。修 adapter_pool 单例跨测试残留 (unit/conftest autouse 清理)。B/C 类留 v6.24。
- **D2 conversation_config 子结构值对象化**: `GitSyncConfig` VO + `LoopConfig` 自 agent_loop 迁入 domain (+from_conversation_config/from_dict, 默认值经 VO 实例单一源, drift guard 对齐)。Project 加 `git_sync_config()`/`loop_config()` 访问器; session_manager + execution_helpers 两处裸读收口。核实实际裸读 2 站点 (非"7+处")。20 单测。
- **D3 scanning 端点集成测试 (15)**: status/start/stream 三端点全覆盖。核实推翻"scan_manager 难 mock 需重构" — 路由 lazy import 可 monkeypatch 注入 testdouble, 零生产代码改动。

### Fixed — 集成套件 flaky + 慢 (F1, 计划外)
- **F1 集成套件 15min+flaky → 33s+216 全绿**: 双层根因 — (1) mock_llm 仅 patch `create_llm_adapter` 漏 generate 路径 (走 `acquire_for_project`→`create_llm_adapter_from_config`, 未 mock→真实 GLM); 修: 同时 patch 两工厂。(2) **integration/conftest 漏 adapter_pool 清理** (G1A 仅给 unit 加), 前测试缓存真实 adapter 污染后测试 (mock 对已缓存 adapter 无效); 修: mirror unit autouse 清理。test_pipeline_e2e/test_agent_registry_sync 多源 flake 同根因一并消除。

### Changed — 评估/澄清
- **D1 A .env 前缀语义整理 (非 breaking)**: 核实"触发 pydantic forbid"已不触发 (config.py 无 model_config, 默认 extra=ignore) → D1 退化为清晰度。文件头修正前缀语义 + 5 compose infra 变量标注。B 类重命名 breaking 大留专项。
- **G1 B/C 架构决策 (定 v6.24)**: C 类 gate/validator 纯函数注入 `adapter` (保持纯函数+零 DB 耦合); B 类 template services 复制 G1 A 模式。

### 质量检测
6.1-6.7 全过 (6.3 grep 不匹配为 pydantic 前缀假阳性, 零 config 改动)。详见 v6.23.0-snapshot.md。基线: ruff0 / unit 2277 / integ 216 (33s 确定性) / tsc-b0 / vitest97。

## [6.22.0] - 2026-07-01 — v6.21 遗留收尾 + 扫描链路修复

### Added — worker/扫描凭证链路接 DB + 扫描修复
- **D2 worker 凭证链路走 DB**: `acquire_worker(llm_config)` 接受 D1 透传的 llm_config, 复用主凭证 + `settings.worker_model` 覆盖 model (cheap), ephemeral 不缓存; None 时 env 兜底。调用方 `orchestration/service.py _run_worker` 传 `self._llm_config`。6 单测。
- **T7 扫描接 DB 凭证 (计划外)**: scanner_analysis 5 处 `acquire()` → `acquire_for_project(llm_config)`, scan_codebase 路由 `resolve_from_project` 透传。扩展 D1 边界 (原"辅助模块不做"), None 时 env 兜底。3 单测。
- **T8 force=true 强制重扫 (计划外)**: scan_manager 加 `cancel(project_id)`, scan_codebase force=true 时取消旧 task 再 start_scan, scan_status 路由补偿。unit 测试。

### Fixed — 集成测试 + 重试缺陷
- **T5 集成测试 4 失败修复**: 三文件本地 `cleanup` teardown 模式 (yield 在前) 在 v6.16 savepoint 下 commit 退化、DELETE 被外层 rollback 撤销, 从未真正清理 dev DB 预存 openhands 脏数据。提取到 conftest 统一 `cleanup` fixture 改 setup 模式 (DELETE+flush 在 yield 前)。附带 `test_db_empty_seeds_env`/`test_seed_idempotent` 真正测到 env seed 路径。
- **T6 403 重试致 scan 409 (计划外)**: `resilience._retry`/`chat_stream`/`chat_stream_with_result` 对所有异常重试 (含 403), scanner_analysis 5 处 LLM × 3 重试 × 指数退避致 scan task 占位 → `is_running=True` → 再点 409。加 `_is_retryable_error(exc)` helper, 4xx (非 429) 不重试立即抛出。2 单测。

### Changed — 评估决策
- **T2 Project dict 值对象化**: 评估后不做 (pipeline_config ROI 低 / domain_model ROI 负 (LLM 产出) / conversation_config 整体值对象化绑死迁移期兼容结构)。记技术债务: git_sync/loop_config 子结构值对象化留下版本。

### 质量检测
6.1-6.7 全过 (6.6 记录项: scanning 端点端到端 integ 未补, 全局单例难 mock, unit 覆盖核心)。最终基线 ruff0 / unit+integ 2448 passed / tsc -b 0 / vitest 97。

## [6.21.0] - 2026-07-01 — LLM 链路深化 + 技术债清理

### Added — LLM 链路走 DB 凭证 + 前端组件拆分
- **D1 全局默认凭证接通 DB**: `LLMProviderService.resolve_from_project` + `resolve_default_config`, 优先级链 项目 llm_provider_id → 旧明文 → 用户默认凭证 → None(env兜底)。Agent 主链路 (extract_tags/_text_only_stream/orchestration) 走 `acquire_for_project`, env 退化为兜底。推翻方案 A (adapter_pool 全局单例 vs LLMProvider per-user 串台), 改选请求级解析。7 单测。
- **D3 pipeline 路径补 llm_provider_id**: `conversation/service.py` 对齐 unified 路径, 修复 v6.20 L5 遗漏。两处共用 `resolve_from_project` 消除重复。
- **T1 前端 10 组件拆分**: 10 父组件 + 11 parts 文件全 <300, 纯结构搬运零行为变化。

### Changed
- `conversation_context.get_llm_config` 收敛到 `LLMProviderService`, 移除直接依赖 `SqlAlchemyLLMProviderRepository`+`crypto` (减轻 execution 层对 infrastructure 依赖)
- `orchestration.execute` 加 `llm_config` 参数, 3 处 `acquire`→`acquire_for_project`

### 决策
- 推翻 current.md 方案 A (lifespan 注入 _DEFAULT_KEY): adapter_pool 全局单例 vs LLMProvider per-user 隔离串台, 改选请求级解析 + env 兜底
- D1 只改 Agent 主链路核心 (3 处), 辅助模块 (~20 处 create_resilient_adapter) 仍走 env (渐进边界)
- T3 跳过 (hooks.py 纯函数是全项目既定模式, 非聚合违规)
- D2/T2 留下版本 (worker 语义需产品决策 / 值对象化工作量大)

### 遗留
- D2 worker 凭证链路 (worker 语义待定), T2 值对象化, 集成测试 4 失败 (DB openhands 残留, 预先存在) — 留 v6.22

## [6.20.0] - 2026-07-01 — LLM 多厂商凭证管理 + 在线探活

### Added — 多厂商凭证管理 + 在线探活
- **L1 domain**: `domain/llm/` LLMProvider 聚合 (注入式 Fernet 加密, 同签名凭证) + LLMProviderKind (OPENAI_COMPATIBLE/ANTHROPIC) + PROVIDER_TEMPLATES 单一真相源 + repository ABC
- **L2 infrastructure**: `llm_providers` 表 (migration z23, JSONB models + 部分唯一索引 is_default 互斥) + `projects.llm_provider_id` FK 列 + SqlAlchemyLLMProviderRepository
- **L3 adapter 探活**: OpenAIAdapter.list_models (client.models.list() 免费不计费) + verify / AnthropicAdapter.list_models (静态建议, 官方无 list API 诚实降级) + verify (1-token messages.create)
- **L4 application**: LLMProviderService (CRUD + verify_credentials 临时凭证探活返 models + list_models 缓存回填 graceful)
- **L5 链路改造**: conversation_context.get_llm_config 改读 Project.llm_provider_id → DB 凭证 → 兼容 dict (下游零改) + 回退旧明文 dict (向后兼容); Project 加字段 + 端点层可设/读
- **L6 interface**: `/api/llm` CRUD + verify + models + templates 端点 (CurrentUser, GET 不回明文)
- **L7 frontend**: LLMProviderManager (列表+模板+验证按钮+动态模型+设默认) 替代旧静态 MODEL_SUGGESTIONS + 删 temperature/max_tokens 死字段 + 删旧 LLMConfigSection 死代码

### Changed
- config.py LLM 字段降级为 env fallback (DB 多厂商管理为主链路); .env.example 注释指向 DB 管理
- 修 api.listTemplates 重名冲突 (→ listProviderTemplates)

### 决策
- 凭证用户级隔离 (user_id), 加密复用 crypto.py Fernet (同签名凭证, DDD 合规)
- list_models/verify 非抽象方法 (不强制改 ResilientAdapter/TracingAdapter 包装器)
- verify 验临时凭证 (前端传未保存 key, 不依赖保存顺序, 成功顺带返 models)
- Anthropic 静态建议降级 (官方无 list API, 诚实标注不假装)
- get_llm_config 返回兼容 dict (单点改造, 下游零侵入)
- 全局默认走 env 渐进边界 (create_llm_adapter 同步无法读 DB, 项目级已通 DB, 留 v6.21)

### 遗留
- 全局默认凭证读取边界 (L5 渐进): create_llm_adapter() 同步读 env, 未接 DB 默认凭证; 项目级 llm_provider_id 已通 DB, 全局默认走 env fallback。完整接通留 v6.21 D1
- per-phase/worker 选用重映射完整形态, 留 v6.21 D2
- 多 worker 凭证缓存 Redis pub/sub, 留增强
- 质量检测 6.1-6.7 全过; CI 基线 ruff0 / pytest 2430 / alembic z23 双向干净 / tsc-b0 / vitest 97 / build0

## [6.19.0] - 2026-06-30 — 原生客户端平台扩展（Windows → iOS → 鸿蒙）

### Added — 三平台构建/签名/分发链路
- **T1 执行后端真相源**: `domain/sandbox/execution_backend.py` `BuildExecutionBackend` (DOCKER/CI) + `TARGET_BACKENDS` 全登记; 裁决方案 A (CI 编排), 不扩 `SandboxRuntime` ABC
- **T2/T5/T8 artifact 显式建模**: `BuildArtifactKind` 簇 (MSI/EXE/IPA/HAP/APP) + `KIND_SIGNER_TYPE` + `TARGET_ARTIFACT_KINDS` + `EXTENSION_KIND`, 跨真相源一致性测试守护
- **T3/T6/T9 构建目标**: `TAURI_WINDOWS`/`CAPACITOR_IOS`/`HARMONY_HAP` + 双真相源登记 + `for_type` 分支 + CI workflow matrix (windows/macos/harmony) + build step (坑1坑2真实化: 鸿蒙 self-hosted / iOS unsigned `.app`)
- **T4/T7/T10 签名器**: `SignerType.WINDOWS`/`IOS`/`HARMONY` + `IosSigner`/`HarmonySigner` + `enc_ios_creds`/`enc_harmony_creds` + migration z20; `.app` 签名歧义修复 (`_detect_sign_targets` 加 `build_target` 消歧)
- **T3-g Agent→CI 接缝**: build 工具 (CI target 专属) + `BuildOrchestrationService` (`dispatch_build`/`await_build`) + `GitHubActionsClient` + source_url S3 presigned
- **T11 前端透出 + 就绪检测**: 三平台卡片 + 就绪灰显 + `BuildTargetReadinessService` (静态+探活 GHA verify_token + S3 head_bucket, 缓存后台刷新) + `GET /build-targets`

### Changed — 可观测性 + 投产健壮性
- **A1-A3 可观测**: access log + `/ready` 探针分离 (DB+Redis+S3) + `/metrics` Prometheus (HTTP 指标 + Agent 任务耗时)
- **execution_engine 拆分**: 483→325 行, `run_autopilot` 抽 `autopilot.py` `AutopilotMixin`
- **M1 migration 漂移清零**: review_feedbacks 漏 import 修正 + ~12 model 补 index/UniqueConstraint 对齐 DB + z21 consolidation, alembic check 干净
- **M4 BaaS 自动装配端到端验证**: schema/表/RLS 真建 + 可观测加强 (baas-status 端点+前端卡片 / Prometheus metrics)
- **投产门禁修复 (续13)**: A1 注册用户默认 admin 越权 (role 默认 MEMBER + 首用户特例 + admin 提权 + z22) + A2 `/metrics` bearer token + B5 限流切 Redis + B6 pod graceful + B7 ingress TLS + 部署 runbook/monitoring 工件; 撤 B5 虚假降级 (fail-fast) + 崩溃友好提示缺省页

### 决策
- 新平台构建走 CI 编排 (方案A), 不扩 `SandboxRuntime` ABC (契约错配: 同步单命令 vs 分钟级异步 batch + 文件产物)
- 新增 BuildTarget 同步 12+1 处注册点 (`execution_backend.TARGET_BACKENDS` 为第 13 处真相源, 未登记抛 ValueError)
- 就绪检测真实探活 + 缓存后台刷新 (乐观策略 `verified=None` 判 ready 避免误灰显)
- 延续 v6.1 mock 验证签名链路模式 (端到端 blocked 于凭证时命令构造+链路用 mock 验证)

### 遗留
- M2 三平台构建端到端 (硬阻断, 用户凭证: `ARC_GHA_TOKEN` + 云端 `ARC_STORAGE_*`; iOS 需 macOS runner + Apple 账号; 鸿蒙需 self-hosted runner + DevEco)
- 签名分发端到端 (T4/T7/T10 独立 blocked: Windows EV 证书 / Apple Developer + provisioning / 华为 .p12+.cer+.p7b)
- OpenHands/Codex 真注入 blocked 于 runtime 环境
- 质量检测 6.1-6.7 全过; CI 基线 ruff0 / pytest unit 2166 + integ 177 / tsc-b0 / vitest 91 / build0 / alembic check 干净 (head z22)

## [6.18.0] - 2026-06-29 — 投产治理升级

### Changed — 投产阻断项消除 + 验证闭环
- **CI builder 镜像发布**: `docker-publish.yml` 新增 `build-builder-images` matrix job (tauri/web/android-builder → ghcr, release tag 触发); config + .env.example 补生产覆盖映射 (`ARC_SANDBOX_BUILDER_IMAGES`)
- **MCP 执行链收尾**: `HttpMcpTransport` 支持 `text/event-stream` 流式响应解析 (兼容 `application/json`, 修 transport=sse 配通但不支持的契约 bug); ClaudeCode `_Session` 绑定 mcp_config path + `close()` 删临时文件 (不靠 OS tmpdir 兜底)
- **T3 import 环治理**: LLM/EventBus/Sandbox/Context 拆出契约/工厂/工具模块 (`llm_types`/`llm_factory`/`eventbus_contract`/`eventbus_factory`/`runtime_base`/`token_utils`), import 环 5→0; `llm_adapter` 保留 re-export 向后兼容, 旧调用方零改
- **T2 alembic lint**: 历史迁移 import 顺序规整 + `pyproject` per-file-ignores 豁免长行 (`alembic/versions/*.py`)
- **T4 配置对齐 + 模板 bug 修复**: .env.example 双向对齐 Settings 字段; 修复 `ARC_SANDBOX_BUILDER_IMAGES` 空值回归 (dict 字段空值 pydantic 解析失败, 改回注释留空用默认注册表); `ARC_WORKERS` (uvicorn 启动参数, 非 arc Settings) 改注释说明, 消除 .env 文件源 forbid 炸点

### 决策
- import 环用契约/工厂分离 + re-export (旧调用方零改, 避免大面积改 import)
- v6.18 定位投产治理升级, 不新增产品功能 (上线前阻断项优先, 产品演进与治理解耦)
- `.env.example` dict 类型字段留空用注释而非裸空值 (`=`), 符合 pydantic-settings 解析约束

### 遗留
- OpenHands/Codex MCP 真注入仍 blocked (需 runtime 环境: OpenHands localhost:3000 / Codex api_key 未配); 仅 ClaudeCode --mcp-config 真注入
- infra 变量前缀设计债务: root `.env.example` 混合 arc 配置 + compose infra (`ARC_DB_PORT`/`ARC_WORKERS`/`ARC_PORT`/`ARC_*_IMAGE` 用 `ARC_` 前缀, cwd=root 读 .env 跑 arc 触发 forbid) → P2
- 质量检测 6.1-6.7 全过; CI 基线 ruff0 / pytest unit 2051 + integ 149 / tsc-b0 / vitest 89 / build0

## [6.17.0] - 2026-06-29 — Skill 注入执行链（架构统一 + 工具集补全）

### Added — skill 对称注入执行链
- **T1 数据模型**: ToolSpec 值对象 (source=inline|mcp); SkillLoader.load_full 返回 SkillContent (prompt + tool_specs, yaml 解析 SKILL.md frontmatter tools); TaskContext 加 skill_specs/tool_specs/mcp_servers 字段, to_markdown 输出技能规范段
- **T2 架构统一 (核心闭环)**: CapabilityProvider.load_phase_skills (对话/执行共享 _collect_active_caps, 单一真相源); TaskContextBuilder.build 接 phase_type; session_manager 透传 — skill 真正进 coding agent 执行链
- **T3 Codex 工具注入**: CodexAdapter._build_tools 把 inline function 注册为 /responses tools (Responses API 顶层格式), code_interpreter 兼容

### Added — MCP 消费侧
- **T4**: McpClient (stdio + http 传输, JSON-RPC 2.0); McpLoader 转 ToolSpec(source=mcp); CapabilityType.MCP 激活 + is_mcp property; load_phase_skills 集成 mcp
- **T5**: ClaudeCodeAdapter --mcp-config (真注入, agent 直连 MCP server); OpenHands/Codex 按 agent 能力降级 (to_markdown 指引文本)

### Changed
- **T6**: capability config 支持 source/directory/content (tools 在 SKILL.md frontmatter, inline textarea 已支持); MCP hint 更新 + 配置提示; PhaseCapabilitiesSection 已支持选 skill/mcp; pyyaml 显式声明 (避免 transitive)
- 质量检测 6.1-6.7 全过; CI 基线 ruff0/pytest unit 2044+integ 149/tsc-b0/vitest 7

### 决策
- 统一 provider 取数层, 不合并产物形态 (ContextAssembler→system prompt 对话 / TaskContext→markdown 执行, 各自契约不变)
- 工具集按 agent 能力分发 (Codex function / ClaudeCode --mcp-config / OpenHands 降级指引), 不抹平不对称
- load() 向后兼容, 新增 load_full() (现有 8 测试 + provide 不破坏)

### 遗留
- MCP 真注入仅 ClaudeCode (OpenHands per-session config 不支持 / Codex fire-and-forget 无 function call 路由, 降级指引文本)
- McpClient HttpMcpTransport 为简化版 (单次请求/响应, 非完整 SSE 流)
- 端到端真实 agent 验证待环境就绪 (OpenHands localhost:3000 未启动 / Codex api_key 未配); 单测+集成测覆盖注入逻辑

## [6.16.0] - 2026-06-29 — v6.15 遗留技术债务清理

### Changed — process_constraint 单一真相源收敛

- **T1 execution_mode 字段下线**: 删 todo/project entity.execution_mode + set_execution_mode + ORM 列 + repository 映射; TodoResponse 透传 process_constraint (resolve_names batch 查 project, 零 N+1); 独立 todo fallback STRICT; workspace_service create/apply 删 execution_mode 协调; alembic z19 drop column (z18 已回填 process_constraint, drop 安全); 前端 8 处改读 process_constraint + 删 ExecutionMode type/EXECUTION_MODE_LABELS 死代码
- **6.1 死代码补清**: drop column 后 ExecutionMode class + ProcessConfig.from_execution_mode 无生产调用, 删除

### Changed — gate 阈值同源 / 死结构清理 / 测试隔离

- **T2 strict 阈值同源 GateProfile**: evaluate_gate 加 constraint 参数, score<7 与 缺口>=3 改读 get_profile(constraint).score_threshold/structural_short_circuit (消除与 STRICT profile 巧合相等); ProjectContext 加 process_constraint
- **T3 删 DELIVERABLES_BY_CONSTRAINT 死结构**: 删三别名 + dict (三档恒等 REQUIRED_DELIVERABLES); conversation_strategy 两处 fallback 改用 REQUIRED_DELIVERABLES; needs_reorder 非死逻辑保留
- **T4 测试 DB 事务隔离**: conftest db_session 改 join_transaction_mode=create_savepoint, test user flush 不 commit, teardown rollback 外层事务全部撤销; 根治 test_capability_api 偶发 409; 共享 dev DB 安全不 truncate

### 决策

- process_constraint 单一真相源, todo 不持 constraint 字段 (TodoResponse 透传 project.process_constraint)
- gate 阈值读 GateProfile, 不硬编码 (同源非巧合相等)
- 测试 savepoint 隔离优于 truncate (共享 dev DB 不破坏真实数据)

## [6.15.0] - 2026-06-28 — 过程约束依赖守卫治理

### Changed — 三模式依赖约束统一为硬不变量

- **T1 DAG 补全**: 补 5 条依赖边 (prototype→tech_architecture/app_code、app_code→dev_report/test_report、experience_card→dev_report), 堵"没原型写代码/没代码报告测试"的空中楼阁; 加无环校验
- **T2 废除 soft 放行**: 删 GateProfile 的 dependency_block_mode/dependency_hard_block + ConversationGateResult.dependency_warning; 依赖约束三档 (strict/moderate/free) 统一硬阻断, 与 constraint 无关
- **T3 STRICT 补 DAG 守卫**: `_evaluate_phase_gate` 先过 DAG 再 evaluate_gate, 覆盖 skip 阶段后产出依赖未满足 artifact 的缺口 (phase 顺序检查只拦"前置 phase 完成", 不拦"前置交付物达标")

### Changed — ProcessConfig 死字段清理 + 模式守卫

- **T4 ProcessConfig 死字段清理**: 删 gate_strictness/auto_extract/require_explicit_confirm/show_phase_ui 四字段 (前后端零业务消费, gate 行为由 GateProfile 接管); 退化为 constraint 容器; create/update 双构造路径收敛, from_execution_mode 成为单一映射点
- **T5 后端模式守卫**: pipeline 5 写操作 (start_pipeline/start_phase/confirm/skip/rollback) 接入 `_require_pipeline_mode`, FREE/MODERATE → 409 mode_mismatch; 真相源 todo.project→project.process_constraint, 无 project 回退 execution_mode。conversation send_message + 读/artifact 操作不守 (跨模式共享)
- **T5 附带修复 create 持久化 bug**: `ProjectRepository.create` 漏写 process_constraint/process_config (DB 用 ORM default "free" 覆盖)。潜伏已久, 守卫依赖 process_constraint 时暴露
- **T6 历史数据回填**: z18_backfill_process_constraint migration 实测修正 959 个 pipeline→free 为 strict

### 决策

- 依赖约束 (DAG) 是三档共享硬不变量, 不该由模式开关决定 — dependency_block_mode 是设计错误
- FREE 的"自由"= 在可推进集合 (入度为0节点) 里自由选下一个, ≠ 无视依赖强行跳
- DAG 是交付物顺序唯一真相源; STRICT phase 顺序检查 (编排) 与 DAG 守卫 (依赖) 职责不同, 共存不合并
- ProcessConfig 退化为 constraint 容器, gate 行为由 GateProfile 接管
- 模式守卫真相源 = project.process_constraint (单一源), 不往 todo 加 constraint 字段 (避免第三处重复存同值)

### 遗留 (技术债)

- execution_mode deprecated 下线 (P2): 前后端契约仍用, 与 process_constraint 双源未收敛
- strict 阈值双存 (P2): pipeline/gate.py:147 硬编码 score<7 绕过 GateProfile
- DELIVERABLES_BY_CONSTRAINT 死结构 (P2): 三档同列 + reorder 空操作
- 测试 DB 隔离 (P2): conftest db_session commit 后无法 rollback
- create bug 教训: repository 新增持久化字段必须同步 create + to_entity 两处

## [6.14.0] - 2026-06-28 — 项目设置 UX 整理

### Changed — 环节能力配置默认收起

- **T1**: PhaseCapabilitiesSection 自带折叠 (复用 LLMConfigSection 模式: showAdvanced + ChevronDown rotate-180), 移到「项目规范」卡片下方默认收起。纯前端, 后端零改动 (默认行为不变: 7 环节始终存在, 每环节默认 0 能力)

## [6.13.0] - 2026-06-28 — 签名链路真实化 + 凭证预留 (A 限定版)

### Added — 签名链路真实化 + 凭证配置项预留

- **T1 P3 修复 + 凭证预留**: SigningCredentials 加 `apple_id` (Apple ID 邮箱), has_apple() 含之; AppleSigner notarytool --apple-id 用 apple_id (非 team_id, 修 v6.1 P3), --team-id 保持 team_id; 注释去 mock 措辞 (命令构造真实, L3 已证 android 同理); 测试级联补 apple_id + test_apple_missing_id_not_complete (P3 回归) + notarytool --apple-id 断言
- **T2 L3 固化测试**: test_android_build_real.py (slow) 真实 capacitor 7 → assembleRelease → apksigner sign/verify v2 通过; android 工具链 smoke; pyproject addopts `-m "not slow"` 让 slow 默认 skip
- **T3 文档收尾**: current.md 方向落定 A 限定版 + 任务表/依赖图/验证标准

### 决策

- 方向 A 限定版 (签名链路真实化 + 凭证预留) — 候选中选 A: 接 v6.12 闭环的 android 构建链路上真实签名验证 + 修 v6.1 P3 凭证配置遗留; mac/win 真实签名卡凭证/环境, 本版只做凭证预留配置项
- notarytool --apple-id 用 apple_id (Apple ID 邮箱) 非 team_id — 修 v6.1 P3 误用; 用户配齐 apple_id+developer_id+team_id+app_password 即可真实签名
- L3 证伪 "AndroidSigner 是 mock" — 真实端到端 (assembleRelease → apksigner sign SIGN_OK → verify v1/v2/v3 全 true), 真调 apksigner
- slow 测试默认 skip (addopts -m "not slow") — 5min 级真实构建测试不污染日常 pytest

### 遗留 (技术债)

- mac 真实签名验证 — 需 Apple Developer ID 证书 (用户私有), 待凭证
- win 真实签名验证 — 需 Windows runner (本机 macOS 跑不了 signtool)
- runtime.py:107 application→infrastructure.eventbus 惰性 import — v6.7 既有, 非本版本引入

## [6.12.0] - 2026-06-28 — 容器构建链路扩展（web + android capacitor 镜像）

### Added — BINARY_APP 全平台容器化构建

- **T1 波次2 web-builder**: BuildTarget.WEB 激活 + 注册 (BINARY_APP, WEB)→arc/web-builder:latest + for_type WEB 分支 + web-builder.Dockerfile (node:20-alpine+构建工具链) + smoke (vite build 产 dist)
- **T2 波次3 android-builder**: BuildTarget.CAPACITOR_APK 激活 + 注册 + for_type CAPACITOR_APK 分支 (npm build+cap copy+cap build) + android-builder.Dockerfile (JDK21+SDK+NDK r26+Gradle8.7+cap7.6.7, 强制 amd64) + smoke (gradlew assembleDebug 产 app-debug.apk 3.9MB)
- **T3 build_target 端到端**: ProjectCreate schema 加 build_target + route 透传 + service 注入 sandbox config (capacitor_apk 额外 memory 4096) + 前端 CreateProjectModal 三 target 选择器 + types BuildTarget
- **T4 质量检测**: 6.1-6.7 必修项通过, 归档

### 决策

- WEB target 绑 BINARY_APP (化解 v6.0 "接近 STATIC_SITE 重复" 矛盾) — BINARY_APP 三构建形态: tauri_linux/web/capacitor_apk
- android 镜像强制 amd64 (aapt2 x86_64 ELF, arm64 Rosetta 缺 x86 ld-linux; x86 CI 原生, Apple Silicon 经 Rosetta)
- JDK 21 (capacitor 7 要求 source 21, JDK17 不够)
- capacitor kotlin 版本统一归项目配置 (非镜像缺陷)
- capacitor_apk 注入 memory_limit_mb=4096 (构建重)

### 遗留 (技术债)

- capacitor kotlin 项目配置 (stdlib 1.8.22 vs jdk8 1.6.21 重复类) — 用户项目配置, BUILD_GUIDE 提示
- android release build checkReleaseDuplicateClasses — 同上, smoke 用 debug apk 验证工具链
- runtime --shm-size 未验证 (本地 --shm-size=2g 通过, 默认 64m 待 x86 CI 确认)
- mac/win 原生构建需原生 OS runner (v6.0 决策)

## [6.10.0] - 2026-06-28 — B 流程引擎内容编排（methodology/prompt/gate 可配置）

### Changed — 环节逻辑内容显性化

- **TD-1~4 技术债清完** (v6.11 遗留): tool_loop.run() 拆分+补测试 / 测试文件拆分 / tests ruff F841/F821 清理 / opensandbox 本地处理
- **T1 方案设计**: 配置文件方案 (Python 常量模块载体, 零新依赖) + 三类内容迁移映射
- **T2 methodology 显性化**: `application/context/content/methodology.py` — free baselines + moderate prompt + prototype_guide, get_methodology_prompt_for_constraint/MethodologyProvider 改读 content
- **T3 phase_prompts 显性化**: `content/phase_prompts.py` — PHASE_SYSTEM/EXTRACTION_PROMPTS + _PHASE_INFERENCE_PROMPT, 3 处消费方改读 content
- **T4 gate 显性化**: `content/gate.py` — DELIVERABLE_REQUIRED_FIELDS + GateProfile 阈值 + GATE_EVALUATION_PROMPT, conversation_gate/gate 改读 content
- **T5 registry 统一**: `content/registry.py` 统一入口 + .get fallback, 9 处消费方接通; 屏蔽组织/模板前端入口 (hidden 可逆); 全量回归

### 决策

- 配置文件方案 (git 版本控制, 无 DB/migration/管理界面)
- Python 常量模块载体 (非 YAML, 零新依赖)
- 内容可编排管道不变; strict 子模块 (clarification_strategy 路由等) 保留代码非内容
- 复用 v6.9 dict+.get fallback 模式; 一次性迁移无运行期双读

### 遗留 (技术债)

- strict 子模块未显性化 (含编排逻辑, 留 backlog)
- 配置载体 Python 常量, 非开发人员无法编辑 (需 YAML+管理界面, 留 backlog)

## [6.11.0] - 2026-06-27 — 投产就绪 + 质量加固

### Added — 投产硬缺口消除 + 质量加固

- **T1 k8s 部署完整性**: 补 db(pgvector)/minio/opensandbox/openhands manifests, 对齐 docker-compose 6 服务, configmap 对齐 config.py 57 字段, kustomize build 通过
- **T2 前端补入口**: organization/template 共 17 端点补 webui 操作入口(client 工厂+页面+路由+导航+index spread)
- **T5 测试补全**: test_deployment_service(13) + test_errors(15); billing(test_quota_service) 已充分
- **T3 领域错误规范化(3 波 49 处)**: 46 ValueError/HTTPException→domain/errors(AppError/NotFoundError/ConflictError), route 删 except ValueError 全局 handler 接管, 状态码精确化(NotFound 404/业务约束 400); 3 系统 RuntimeError 保留(走全局 500 不泄露 detail)
- **T4 超限文件拆分**: 6 文件全拆 <500 行(tools/useConversationSocket/tool_loop/execution_engine/conversation_strategy/artifact_extractor), 公开 API 不变(模块级 re-export 或组合类)
- **T6 清理收尾**: 86 TODO 评估(81 seeds 数据占位+~4 代码 TODO, 无安全/数据丢失阻断) + 质量检测 6.1-6.7 必修项通过

### 遗留 (技术债)

- tool_loop.py ToolAwareLoop.run() 方法 225 行超 80 行(预存, 非本版本引入, 下版本补分支测试再拆)
- opensandbox SDK 本地未装(test_opensandbox_runtime collection 失败, CI 环境有依赖)
- tests 目录 246 处预存 ruff 问题(CI 不跑 tests ruff, 可独立 `ruff --fix tests` 清理)

## [6.9.0] - 2026-06-27 — test_health修复 + artifact显式建模 + 按类型编排流程 + 能力升级 + 前端体验

### Added — 构建产物显式建模 + 按类型编排 + 前端体验

- **test_health 时序污染修复**: 方案E conftest monkeypatch 全局 factory 隔离(全量连跑不再时序污染)
- **artifact BUILD 显式建模**: BUILD artifact domain+service 锚点 + extractor 自动抽(仅 BINARY_APP) + _resolve_build_status 双读(BUILD优先→build_evidence→app_code/prototype→deploy_content, 双读兼容存量)
- **按类型编排流程(A)**: DELIVERABLES_BY_TYPE(STATIC_SITE去app_code, BINARY_APP加build) + PHASES_BY_TYPE(两类型全7阶段, 预留) + is_deliverable_visible + tracker.required 按类型裁剪 + app_code 类型过滤
- **skill 多来源(C1)**: SkillLoader source=inline(内联文本, 无需SKILL.md)/directory
- **前端体验**: CapabilityEditorModal skill source 结构化(directory/inline) + CapabilityManager 按 type 分组(agent/skill/mcp) + Build renderer(构建状态徽章, 只app类由后端 tracker.required 裁剪保证) + ArtifactType 类型补全
- **_resolve_build_status 双读单元测试**(7个, 补④核心 94169c5 遗漏) + CapabilityEditorModal(7) + Build(3) 测试

### 决策

- A 类型级流程模板(保7阶段骨架, 按 ProjectType 裁剪交付物, 非完全自定义阶段)
- artifact 双读兼容(prototype content 保留 build_status, ④消费改造后废弃)
- ④消费点分流核查: 四消费点(build_gate/_deploy_project/_detect_sign_targets/Signer.sign)已由双读兼容+类型路由+隐式skip覆盖, 无需新代码
- B(流程引擎内容编排 methodology/prompt/gate 可配置)分离 v6.10

## [6.8.0] - 2026-06-26 — 能力注册表: Agent/Skill 声明管理 + 环节级配置

### Added — 能力运行时入口补全

- **能力注册表骨架**: domain/capability 值对象 + CapabilityModel + migration z17 + CapabilityService + /api/capabilities CRUD(读登录/写admin)
- **agent 声明 env→DB 迁移**: AgentRegistry 声明驱动重构(双读兼容, DB 空回退 env) + lifespan sync
- **skill SKILL.md 加载器**: frontmatter 解析 + 容错
- **环节级能力配置**: pipeline_config.phase_capabilities(固定7阶段) + PUT route(admin, 单phase增量) + list_by_ids
- **执行按环节注入**: CapabilityProvider 走 ContextAssembler Provider 管道(第10个 provider), skill 注入 prompt / agent 影响可用集合
- **门禁 LLM 延伸**: conversation_gate capabilities_section(charter 门禁同构)
- **前端能力管理页**: SettingsPage 能力管理 section(CapabilityManager 列表+toggle+删除, CapabilityEditorModal 新增/编辑)
- **前端环节配置 UI**: SettingsTab PhaseCapabilitiesSection(7阶段×能力勾选, 即时保存)

### 决策

- 统一能力注册表(agent+skill 复用 SIGNERS 模式, MCP 预留 type 不实现 loader)
- 环节内能力可配(固定7阶段), 非环节自定义(保研发链路定位)
- 执行注入走 Provider 管道非 execution_engine(plan 原写注入点经核查该方法无 phase 不组 prompt)
- 门禁走 LLM 延伸非规则引擎; type-phase 不硬匹配(skill 通用性, LLM 软约束)
- 顺带修 update_pipeline_config 重置→增量 merge + 全局 DomainError→400 handler

### 遗留

- artifact_extractor 622 行(警告区) / pipeline 模式 capabilities_section 传空 / agent 环节级选配未做 / 能力热加载未做 / 前端 config JSON textarea — 均 P3

## [6.7.0] - 2026-06-26 — 运行时入口补全: 对话双轨统一 + 凭证API + skill热重载 + charter门禁

### Added — v6.6 收尾后无自然驱动版本, 收敛 4 项运行时入口

- **T1 对话执行双轨统一**: ConversationService 委托 ExecutionEngine, service.py 498→135 行, 删~360 行死代码(PURPOSE_TO_PHASE/_build_system_prompt/_tool_aware_stream)
- **T2 签名/分发凭证配置 API**: DeployService.configure_*_creds + 3 route, 接通零调用方 crypto.encrypt, deploy 签名不再恒 skip
- **波次2 skill 运行时配置热重载**: AgentRegistry.reload() 原地重建 + 修 LLM 持久化 env_prefix 不一致致配置重启丢失
- **波次3 charter 遵守度门禁**: evaluate_conversation_gate 加 charter 参数, _run_llm_review 注入 charter_section, charter 违规可阻断推进
- **T0a/T0b 基线修复**: k8s 部署文档断裂(README K8s 小节) + 前端死代码(api/client/templates.ts 8 零调用方法)

### 决策

- 对话执行统一到 ExecutionEngine, 禁止再自实现 _tool_aware_stream
- 凭证加密 domain 回调注入, infrastructure 不直接持 domain
- charter 门禁走 LLM 延伸非规则引擎; pipeline 模式不评 charter(记技术债务)

### 遗留

- T4 project_member repository(P2, 聚合边界未定) / v6.0 波次2-3 构建链路(P2) / artifact 显式建模(runtime 前置) / 凭证清除 DELETE(P3) / pipeline charter 评审(P3) / test_health 时序污染(P2)

## [6.6.0] - 2026-06-25 — 代码质量修复收尾

### Changed — 全项目深度审计质量修复

基于全项目深度审计(后端 545 + 前端 117 文件)的质量修复收尾, TDD 路径(补单测→拆分→行为保持)验证可行, 累计修 2 真实 latent bug:

- **P1 架构清理**: 删后端死代码 experience/analytics.py(218 行零引用) + 前端 6 死代码文件 + inspector 孤儿; k8s 占位符 :placeholder → :latest; 移除冗余依赖 websockets
- **P2 route 逻辑泄漏抽 service**(+32 单测): 新建 SettingsService/TemplateService, 扩展 ExperienceService(create/update), 3 处 route 降至参数校验+调用
- **P2 repository 接口漂移补齐**: domain 补 AbstractUserRepository + AbstractOrganization(Member)Repository, infrastructure 继承
- **P2 前端清理重构**: Field 重复合并→shared.LabeledField; vite esbuild.drop; globPatterns 移除 png; ProjectDetail 抽 SuggestionsPanel(405→329); TodosTab props 聚合 32→15(+4 组件单测); useConversationSocket onmessage 180 行 switch→分发器+4 子函数(全<80 行, +14 单测)
- **P2 service 方法 TDD 拆分**(修 2 bug): deploy(108→45)/extract_from_todo(112→36)/confirm_phase(100→33, 修 GateResult UnboundLocalError)/execute(102→49, 修 ToolLoopEvent NameError)
- **P3 mcp _call_tool if 分发改字典表**
- **T1 ExperienceInjectionLog 孤儿表清理**: 新增 z16 migration drop(down_revision=z15, downgrade 复用建表) + 删 model。revision id 受 alembic_version.version_num varchar(32) 约束须 ≤32 字符
- **T2 artifact-renderers lazy 统一**: 11 renderer 顶层 import→lazy()+Suspense 自包含, 12 renderer 切独立 chunk, 首屏不再加载

### 决策

- **TDD 重构路径**: 补 characterization 单测→拆分→行为保持, 测试网保护下修真实 bug
- **评估保持不强拆**: execution 4 文件 500-800 警告(职责内聚, 单方法未超 80); useConversationSocket 523 行(hook 天然复杂度); 聚合边界收敛(application service 多聚合协调是合理模式)
- **lazy 自包含 Suspense**: 调用方零改动, 杜绝漏包运行时报错

### 遗留

- T4 project_member repository 接口(P2, 需先定聚合边界) — 待 v6.7
- T3 GitHubSection 19 props 聚合(P3, 评估负收益可能)
- execution 4 文件 500-800 行 — 待超 800 或明确动机再拆

## [6.5.0] - 2026-06-25 — execution 层拆分评估 + 测试补全 + config 核对

### Changed — v6.4 遗留 3 项技术债务清理

v6.4 收尾后的健康度修复, 无新功能:

- **execution 层文件拆分评估** (T1): 4 文件(tools 601/execution_engine 551/artifact_extractor 546/tool_loop 509)均 500-800 警告区间(非>800必修), 职责内聚。tools.py 拆分需引入兼容间接层(execution_engine 直接 import 私有 _run_command), 减行收益低于复杂度成本, 评估结论保持记债务
- **ui_design_methodology domain 单测补全** (T2): 13 单测覆盖 wireframe 缺 user_story 检查 + 三态 gap(empty/loading/error, 含 v6.4 T5 补的 error state gap)。v6.4 遗留"ui_design 无 domain 测试"债务清零
- **config↔env 核对** (T3): 实查差 5(非估的 3), supabase×4 字段(db_url/schema_prefix/anon_key/api_url)补 .env.example BaaS 段; sandbox_builder_images(dict 类型)已注释说明。补全后 config 52 vs env 51, 仅差 dict 类型(合理)

### 决策

- **不强拆 execution 层**: 500-800 警告区间职责内聚, tools.py 拆分需重新 export 保持 execution_engine 对私有函数的直接 import 兼容, 间接层成本 > 减行收益
- **ui_design 单测零 mock**: domain 层直接构造 content dict 验证 validate_ui_design 行为
- **config↔env 精确核对**: 用 AST 提取 Settings 字段 + 去 ARC_ 前缀对比, 修正 v6.4 估算的"差 3"为实际"差 5"

### 遗留

- execution 层 4 文件 500-800 行 — 待超 800 或明确拆分动机再拆
- v6.6 方向待定(backlog 无规划, v6.5 无自然驱动)

## [6.4.0] - 2026-06-25 — 债务清理 + prompt-upgrade P2（规则残留 LLM 化）

### Added — 收尾"规则执行式→意图驱动"升级 + 清零 CI 债务

prompt-upgrade P2 (#11-14) 把 execution 层 4 处残留规则执行式判断 LLM 化, 复用 #8-10 的"🟡结构预筛+🟢LLM确认+降级兜底"范式; 清零 main 既有 ruff/tsc 债务让 CI 转绿:

- **#11 事件时态 LLM 化** (T1): architecture_methodology _is_past_tense 字面预筛(🟡) + LLM 判断 DDD 合规(🟢) + 异常回退字面匹配。validate_architecture 改 async 连锁 _check_methodology/_safe_methodology
- **#12 测试失败 LLM 化** (T2): dev_test_methodology 字面预筛 FAIL/ERROR(🟡) + LLM 判断是否真失败(区分测试名/注释字样 vs 实际失败)(🟢) + 降级回退字面
- **#13 route_strategy 空参数修复** (T3): constraint_policy 传入真实 title/description 让关键词路由(NEW_DOMAIN/OPTIMIZATION)生效
- **#14 _infer_phase LLM 化** (T4): prompt_builder 保留 _infer_phase 标准线性流程作预筛 + LLM 推断推进/回退(覆盖非线性返工) + 降级回退预筛
- **ruff 68 债务清理** (T5): 26 文件 E501 折行 + F841×2 死变量(ui_design 补 error state gap 修复三态对称遗漏)
- **前端类型 34 债务清理** (T6): 16 未使用快修 + 18 真实类型(ArtifactEditor/RollbackButton 修 api.todos/projects 调用 bug, toast/confirm 统一 ToastType/ConfirmOptions, UnifiedWorkspaceView metadata 断言+ApprovalDialog props 映射)

### 决策

- **范式统一**: T1-T4 复用 execution/llm_review.py 的 default_llm_review (llm_review_fn 可注入测试), 🟡预筛+🟢LLM确认+降级兜底, LLM 异常不阻断主流程
- **债务清理零逻辑改动**: T5 纯折行/死变量清理, T6 前端删未使用+修真实类型(含 2 处 api 调用 bug 修复)
- **prompt-upgrade 14/14 全清**: execution/context 层判断无规则执行式残留

### 遗留

- execution 层 500-800 行文件 (tools 601/execution_engine 551/artifact_extractor 546/tool_loop 509) — v6.5 评估拆分
- ui_design_methodology 无 domain 测试 — v6.5 补
- config↔env 差 3 字段 (derived, 既有) — v6.5 核对

## [6.3.0] - 2026-06-25 — 项目治理规范传递（交付物初始化声明规范）

### Added — 把 Arc 治理体系作为"基因"传给交付项目

"不同项目类型落地"终局第五步（构建 → 签名 → 分发 → **治理规范传递**）。不传则交付即腐烂：

- **project_charter artifact 建模 + 初始化产出** (T1): ProjectCharter frozen 值对象 + ConventionTemplateProvider abc 接口 + DefaultConventionTemplateProvider 通用意图驱动骨架 (domain/project/charter.py 新)。Project 加 charter 字段 + initialize_charter() 方法。JSONB 持久化 (migration z15)。charter 与 conventions 并存分工 (charter 系统按类型生成治理底座, conventions 用户补充零改动)
- **CONVENTION_TEMPLATES 注册表按 ProjectType 特化** (T2): static_site 特化 (SEO/PWA/性能意图) + binary_app 特化 (签名/分发/跨平台意图, 复用 v6.0-v6.2 成果)。ConventionTemplateRegistry 查表+fallback 通用骨架, 与 v5.9.0 get_distributor/get_prototype_guide 同构
- **两层传递** (T3): ① charter 文本深化把 Arc 4 样治理机制 (版本协议/上下文加载/任务依赖表/质量门禁) 意图驱动化织入通用骨架; ② GovernanceArtifactWriter 落盘交付产物 (CHARTER.md + CLAUDE.md 初始治理文件结构), 让交付项目 agent 能自运转版本切换/质量检测。两处接入 (workspace_service.create_project + github_service.clone_repo 后补落盘)
- **类型差异端到端验证矩阵** (T4): 验证 static_site vs binary_app 贯穿 DB charter → 落盘 CHARTER.md → 落盘 CLAUDE.md 三层类型特化, 特化互斥, 通用骨架共享

### 决策

- **charter 与 conventions 并存分工**: charter=系统按类型生成的意图驱动治理底座 (等价 CLAUDE.md), conventions=用户补充 (保留现状零改动), 两者都注入 AI 上下文, 职责正交
- **意图驱动纪律贯穿全程**: charter/CLAUDE.md 禁 Arc 规则执行式硬规则 ("文件<500行""必须auth""必修项"等), 只给目标+输出契约+上下文。复用 prompt-upgrade #8-10 范式
- **charter 是 Project 内嵌字段非独立 Artifact**: 项目级元数据 (不绑定 phase/todo), 与 domain_model/context_policy 同层
- **交付产物落项目根**: CLAUDE.md 在根 (通用 AI 入口约定) + .arc/governance/CHARTER.md。不预生成空 docs/versions/ 多文件 (agent 按意图自建 .arc/versions/)
- **github 类型异步就绪处理**: local_path 初始空 graceful skip, clone 后补落盘 (仿 scan 触发, 非阻断)

### 遗留

- ruff 既有债务 164 (E501/F401/I001, main 既有非本次引入) — v6.4 T5 清理
- 前端类型错误 34 (TS6133/TS2322 等, main 既有) — v6.4 T6 清理
- charter 升级 UI (initialize_charter 可重复调用覆盖, 但无升级入口) — P3 后续

## [6.2.0] - 2026-06-25 — 商店分发 + 制品分发层（凭证可配置）

### Added — BINARY_APP 构建产物分发层

为 v6.0 构建、v6.1 签名的 BINARY_APP 产物加分发层，"不同项目类型落地"终局第四步（构建 → 签名 → **分发**）：

- **Distributor 抽象 + 分发凭证项目维度加密** (T1): Distributor 契约 + DistributorType + DistributionCredentials 值对象 (domain)。分发凭证复用 v6.1 crypto, 独立 enc_appstore/playstore/tauri_updater_creds 字段。play_key_json 从 SigningCredentials 归位到 DistributionCredentials。migration z13
- **三渠道商店上传器** (T2/T3/T4): AppStoreDistributor (xcrun altool) / PlayStoreDistributor (jose RS256 JWT→OAuth2→Play Developer API v3, 复用已有 jose 不引入 PyJWT) / TauriUpdaterDistributor (httpx PUT)。注册 DISTRIBUTORS, graceful skip
- **制品分发层** (T5): DistributionManifest/ArtifactEntry/DistributionOutcome 值对象 (artifact 显式建模) + DistributionService (build_manifest/distribute/generate 下载页·manifest·latest.json·appcast/publish) + distributor 接入 deploy 流程 (DeployService._distribute, graceful 不阻断) + DB/制品仓双写 + Arc API manifest 路由。migration z14
- **端到端验证** (T6): deploy() 串联验证 (BINARY_APP 触发分发+manifest, STATIC_SITE 不触发, 分发失败不阻断)

### 决策

- **T3 用 jose RS256 不引入 PyJWT**: 复用 pyproject 已有 python-jose (v6.1 引入), 纠正"T3 需 PyJWT"评估
- **play_package_name 补字段**: Play edit API 必需 packageName
- **artifact 显式建模**: DistributionManifest 值对象, DB 持久化 + 制品仓渲染双写
- **签名平台 ≠ 分发渠道**: 两维度独立 (.app→APPLE 签名 + TAURI_UPDATER 分发)
- **distributor 接入 graceful**: 分发失败不阻断 deploy, 产物已落制品仓可手动下载

### 遗留

- Tauri minisign .sig / Sparkle edSignature 真实签名生成 (v6.1 签名不产出, T5 用 signature_id 占位) — P2 待后续

## [6.1.0] - 2026-06-24 — 签名/公证层（凭证项目维度加密存储，非阻塞）

### Added — BINARY_APP 构建产物签名/公证

为 v6.0 打通的 BINARY_APP 构建产物加签名/公证层，"不同项目类型落地"终局第三步（构建 → **签名** → 分发）：

- **Signer 抽象 + 凭证项目维度加密存储** (T1): 凭证非全局 config，而是用户为自己项目配的（Arc 是应用构建平台）。Fernet 对称加密（`infrastructure/crypto.py`），按平台分字段（enc_apple/win/android_creds）。domain 通过回调注入加解密（Project.set/get_signing_creds），DDD 零违规。migration z12_signing_creds
- **三平台签名器** (T2/T3/T4): AppleSigner（codesign + xcrun notarytool --wait）/ WindowsSigner（signtool /f /p /tr /td sha256）/ AndroidSigner（apksigner --ks，app signing keystore 非 Play 上传密钥）。注册到 SIGNERS，复用 sandbox/runtime.py subprocess 风格（提取公共 `_cmd.py`）
- **graceful skip 路由** (T5): DeployService._sign_artifact 按产物平台（.app/.exe/.apk 后缀）检测选 signer，非 build_target 硬编码。tauri linux 的 deb/AppImage 无标准签名 → 不签。凭证未配 → SignResult.skip 不阻断构建
- **mock 验证** (T6): 签名链路激活验证（.app→AppleSigner codesign / 凭证未配 skip / linux 产物不签）。真实产物签名待 v6.0 波次2/3

### Changed

- **cryptography 显式声明**: 从 python-jose transitive 改为 pyproject 直接依赖（crypto.py 直接 import，避免 jose 升级风险）

### 决策

- **凭证项目维度加密存储**: 初版 T1 误做全局 config，用户澄清纠正为项目维度 + 加密
- **签名路由按产物平台**: build_target 硬编码映射 APPLE 语义错误（tauri linux 产物不该 Apple 签名），修正为按产物后缀检测
- **graceful skip 三态**: 凭证未配 → skip 不阻断；签名失败 → fail 记 error 但产物仍上传

## [6.0.0] - 2026-06-24 — 容器化构建 runtime + BINARY_APP 构建链路 + sufficiency 接线

### Added — BINARY_APP 项目类型激活 + 容器化构建链路 + sufficiency 产出门禁

激活 v5.9.0 项目类型框架的第二个类型 `BINARY_APP`（原生客户端），向"不同项目类型落地"终局迈出第二步：

- **#7 sufficiency 接线** (T7): 把躺尸的 `INPUT_SUFFICIENCY_PROMPT` 三维评估(target_users/core_problem/feature_direction)接到 requirement_spec 产出前门禁（用户确认产出前门禁方案，非原推荐 A+B）。职责分离：轮次管引导，LLM 管质量判断。降级放行（LLM 失败 → sufficient=True）。`execution/sufficiency_gate.py`(新) 接入 `ArtifactService.confirm`，pipeline 模式漏检由 evaluate_gate 兜底
- **BINARY_APP 框架激活** (T4): 六处注册点全部激活（v5.9.0 扩展点零框架改动复用）——ProjectType / DeployType.BINARY_ARTIFACT / DeployConfig.for_type(cargo tauri build) / DeployService 路由 / get_deployer / PROTOTYPE_BUILD_GUIDES。schema Literal + 前端类型同步 + **前端 UI 选择器放开**（CreateProjectModal binary_app 卡片选择器，标注"构建需 Docker"）
- **BinaryArtifactDeployer** (T5): 二进制制品落制品目录（不分发，分发在 v6.2）。与 StaticSiteDeployer 差异：不要求 index.html（仅校验目录非空），url 指向制品根。复用 storage 抽象
- **容器化构建链路** (T2/T3/T6 波次1): 三目标(linux/web/apk)按波次拆分, 架构层一次做对。波次1 完成 tauri linux 端到端闭环:
  - `BuildTarget` 维度(domain): TAURI_LINUX 激活, WEB/CAPACITOR_APK 预留(波次2/3 零架构返工)
  - `build_images.py` 镜像注册表 + `policy_resolver` 策略解析: BINARY_APP 默认注入 mode=docker + 镜像推导(runtime 零改动, 既有 12 项真实 docker 测试不受影响)
  - 自建 `arc/tauri-builder:linux` 镜像(rust+node+webkit2gtk+tauri-cli v2, 2.26GB) + Makefile
  - T6 smoke 验证通过(镜像内 cargo 1.96/node v20.20.2/tauri-cli 2.11.3)

### Changed — ConstraintPolicy 死配置清理 (T8)

- `ConstraintPolicy` 11 字段中 10 个零引用(`get_policy` 生产零调用, 门禁职责已由 `gate_threshold.GateProfile` 接管)。保守清理: 仅保留 `methodology_depth` 唯一消费字段, `CONSTRAINT_POLICIES` 轻量化。constraint_policy.py 271→218 行。补 10 测试(原零覆盖, 含防回归断言)

### Fixed — artifact_deployer 路由 bug (断点D)

- `PrototypeDeployer._deploy_project` 原硬编码 `project_type=STATIC_SITE`, 致 BINARY_APP 原型被当静态站点部署。改为按项目真实 project_type 路由(抽 `resolve_deploy_config` 纯函数), BINARY_APP 走 BinaryArtifactDeployer

### 决策

- **三目标按波次拆分**: current.md 原验证标准要求 linux/web/apk 三目标,但内在矛盾。决策: 三目标都进 v6.0 范围但拆 3 波次,架构层一次做对,波次2/3 只填注册表+激活枚举值。迭代的是镜像内容与验证,不是架构欠债
- **镜像推导在 application 层**: policy_resolver 解析策略填入 SandboxPolicy.docker_image,SandboxPolicy 不耦合 project_type(保持"已解析最终配置"职责)
- **前端 UI 放开**: T6 波次1 构建链路就绪后,解除 v5.9.0 "能选但构建不出" 的 UI 限制
- **跨平台范围**: 容器化 linux 沙箱无法构建 macOS .dmg / Windows .exe（需原生 OS）。mac/win 原生二进制推后（原生 runner 或 CI matrix）

### 质量检测

- 单元 1506 passed / smoke 真实验证通过 / 前端 47 passed + tsc 0 error + vite build 绿
- 6.1-6.5/6.7 必修全过, 6.6 测试覆盖全绿
- 波次2(web)/波次3(android) 镜像遗留, 架构已就位独立推进

## [5.10.0] - 2026-06-24

### Changed — Prompt 升级第一批：自由模式门禁 + 部署 + 澄清双轨

落地 prompt-upgrade-plan 路线图 #1-6，把意图驱动能力真正接线（解除 v6.3.0 前置阻塞）：

- **#1 artifact_extractor 门禁分级**：从"仅记录不阻断"改为按 constraint 分级阻断（复用 gate.py 4 层）
- **#2 对话模式门禁接线**：`conversation_gate.py` + `gate_threshold.py`，GateProfile 注册表分级（free≥5/moderate≥6/strict≥7）
- **#3 is_quality_complete 双重校验**：完成判定从"状态标志"升级为"门禁通过双重校验"
- **#4 部署硬门禁**：`trigger_deployment` 从"三重静默 skip"改为 `check_build_ready` 硬门禁，杜绝虚假部署
- **#5 澄清策略路由**：从"固定6层苏格拉底"切到 `clarification_strategy` 三策略路由（按需求类型动态选方法论）
- **#6 autopilot 门禁重试**：从"盲目推进"改为门禁卡点反馈重试 + max_gate_retries=2 截断

### Fixed — 修复 3 个遗留集成红灯（v5.9.0 质检漏检，-x 遮蔽全貌）

- `PHASES_NO_SKIP` 误含 UI_DESIGN 致 `can_skip` 恒 False、skip 功能完全失效（c09f1b5 回归）
- `prototype-bundle` schema 漂移：测试断言旧 `pages`/`new_pages` 字段，实际已升级为 `routes`（前端工程语义）
- `prototype-site/persist` 死测试：端点在 57610a1 重构时移除，原型持久化已由 v5.10 部署断点统一承接

### 质量检测

- 单元 1459 passed / 集成 71 passed / 前端 tsc 0 error
- `execution_engine.py` 538 行（500-800 警告区，记入技术债务）
- prompt-upgrade-plan 进度 6/14，#7-14 属 v6.0/6.1/6.2

## [5.9.0] - 2026-06-24

### Added — 项目类型框架 + 静态站点型落地

把"项目类型"建成 domain 一等公民 + 部署器多态框架，静态站点型端到端落地验证（"不同项目类型落地"终局第一步）：

- **domain**: `ProjectType` 枚举（STATIC_SITE）作为交付形态一等公民，与 backend_type/framework 正交；Project 加 project_type 字段；`DeployConfig.for_type()` 工厂
- **部署器多态**: `Deployer` 抽象基类 + `get_deployer` 工厂；`StaticSiteDeployer` 重构为 STATIC_SITE 实例；`deploy_static_site()` 改为薄封装兼容现有调用点
- **prompt 参数化**: `PROTOTYPE_BUILD_GUIDES: dict[str,str]` 按 project_type 注入，禁止 service/prompt 加 if 分支
- **接口层 + 前端**: schema/route/service 加 project_type；创建表单加选择器（STATIC_SITE 默认且唯一可选，UI 预留）
- **ORM + migration**: `projects` 表加 `project_type` 列（z11_project_type，server_default='static_site' 存量回填）

### 质量检测

- 新增类型仅需在 ProjectType + get_deployer + PROTOTYPE_BUILD_GUIDES 三处注册
- 单元 + 集成测试覆盖全路径

## [5.8.0] - 2026-06-24

### Changed — 技术债务清理（文件超限拆分 + 模板 embed 自动化）

**文件拆分 (T1-T3):**
- `tool_loop.py` 511→413 行：拆出 `tool_loop_metrics.py`（ToolLoopMetrics/Event + 常量）+ `tool_loop_adapters.py`（LLM provider 适配函数）
- `pipeline/service.py` 503→380 行：拆出 `pipeline/hooks.py`（6 个阶段确认 hook 提为模块函数）
- `prompts.py` 504→274 行：拆出 `artifact_schemas.py`（ARTIFACT_SCHEMAS dict 独立）
- 主文件 re-export 保持 import 兼容，纯重构行为不变

**模板 embed 自动化 (T4):**
- `extraction_service.extract_template` 末尾调 `_generate_embedding`（标题+描述+模式作 embed 文本）
- 修复 v5.7.0 遗留：模板匹配不再依赖手动设 embedding
- 失败返回 None（不阻断，匹配时该模板不参与向量搜索）

### 质量检测

- 全源文件回归 500 行强限内（仅剩 seeds 纯数据/api.ts 类型/tools.py 已加例外）
- 全量 1382 测试通过，行为不变

## [5.7.0] - 2026-06-23

### Added — 领域模型模板沉淀（经验引擎核心壁垒）

**模板领域建模 (T1-T2):**
- `domain/template/`: DomainTemplate 实体 + TemplateCategory/Status/Scope 值对象
  - 状态机 draft → confirmed → published → deprecated
  - record_usage (success/failure 调 confidence) + success_rate
  - compute_decayed_confidence (半衰期 180 天, 同 Experience) + is_stale
  - schema_template/entity_patterns/state_machine_patterns/permission_patterns

**模板提取 (T4):**
- `extraction_service.py`: 从 BaasSchema 泛化提取
  - extract_structure (纯逻辑): 表名→占位符, 保留列类型/主键/外键
  - detect_entity/state_machine/permission_patterns 模式识别
  - infer_category 关键词推断分类
  - LLM 生成标题/描述 (失败 fallback 结构化标题)

**模板匹配 (T5):**
- `matching_service.py`: 需求 → embedding → 向量搜索 → 推荐
  - 2x 过宽检索 + 相似度阈值过滤 (同 Experience 质量门控)

**模板套用 (T6):**
- `apply_service.py`: 模板 + 需求 → LLM 适配 → BaasSchema → apply + 记录使用
  - apply 成功/失败都 record_usage (success_rate 统计)

**自动闭环 (T7-T8):**
- release hook: 版本发布后自动从领域模型提取模板草稿
- TemplateProvider: ARCHITECTURE 阶段注入匹配模板推荐 (ContextProvider)
- Project 实体补 user_id (创建者, 模板提取 source_user_id 追溯)

**API + 前端 (T9, T13):**
- `interface/routes/template.py`: CRUD + 状态转换 + 语义搜索 + apply
- migration z10_domain_templates (pgvector embedding 列)
- 前端 TemplateCard + TemplateList (生命周期操作 + apply 确认弹窗)

### 决策

- 模板 vs 经验平行存在 (强绑定骨架 vs 弱绑定参考), ARCHITECTURE 同时注入
- 结构泛化纯逻辑, LLM 仅标题/分类 (失败 graceful fallback)
- 衰减机制同 Experience (半衰期 180 天)

## [5.6.0] - 2026-06-23

### Added — BaaS 运行时层 (Supabase) + MCP server

**BaaS 领域建模 (T1-T8):**
- `domain/baas/`: ColumnDef/TableDef/RlsPolicy/StateTransition/ActionDef/BaasSchema 值对象
  - BaasSchema 强制 `arc_` 前缀 (Supabase schema 隔离约定)
- BaasInstance 实体: provisioning/active/suspended/deleted 状态机
  - apply_model 仅 active 态, model_version 单调递增 (防增量 DDL 回退丢数据)
- BaasStatus/BaasRepository Protocol/ProvisionError/SchemaApplyError/RlsValidationError

**BaaS 基础设施 (T3-T6):**
- `supabase_client.py`: asyncpg 直连 + schema 名白名单校验 (防注入) + SET search_path 隔离
  - DSN 解析: 显式 supabase_db_url > 复用 Arc database_url (dev 同库隔离)
- `sql_generator.py`: BaasSchema→DDL 纯函数 (标识符白名单, 全 IF NOT EXISTS)
- `rls_generator.py`: RlsPolicy→CREATE POLICY (DROP+CREATE 幂等)
- `schema_provisioner.py`: CREATE SCHEMA + _meta_* 元模型表 (借鉴 XSpace)

**BaaS 编排 (T7-T8):**
- `BaasService`: provision (幂等) + apply_model (逐表 DDL+RLS) + introspect
  - apply 后自动跑 RLS 校验 (T17)
- `DomainModelApplier`: DomainModelSnapshot→BaasSchema 转换
  - 聚合→表, 字段→列, id→UUID 主键, 无 id 自动补, 默认 RLS

**接入编排 (T10-T12):**
- Agent BaaS tools: supabase_provision / execute_sql / get_domain_model
- ARCHITECTURE 阶段 hook: 领域模型提取后自动 provision BaaS (失败不阻断)
- DEVELOPMENT 阶段: APP_CODE.backend_type=supabase 时注入 VITE_SUPABASE_* 到前端 .env
- migration z9_baas_instances: baas_instances 表

**安全与测试 (T16-T17):**
- `rls_validator.py`: 5 项 RLS 安全检查 (借鉴 XSpace), 不阻断返回 warnings
- 集成测试: provision→apply→introspect 真实 PG 全链路 (4 项)
- models/__init__.py 补注册 DeploymentModel (v5.4.0 历史欠账)

**MCP server (T18-T19, v5.5.0 deferred):**
- POST /api/mcp: JSON-RPC 2.0 (initialize/tools/list/tools/call)
- tools: arc_list_artifacts / arc_get_artifact / arc_update_artifact
- 复用 Arc JWT 认证, update 走 filter_editable_fields 白名单

### 决策

- T9 不做 DomainModelSnapshot 扩展 (T8 已证明可从 aggregates/fields 推导, 加 tables 会双事实来源)
- MCP 用原生 endpoint 非 Higress to-MCP (配置语法无法在线核实, 凭记忆写不负责任)

## [5.5.0] - 2026-06-23

### Added — DEVELOPMENT 产物补全 + 编辑能力暴露

**Artifact 显式建模 (T1-T6):**
- `ArtifactType.APP_CODE` — DEVELOPMENT 阶段的机器可解析代码工程元数据
  - `project_dir / tech_stack / framework / build_command / run_command / entry_points`
- `ArtifactType.SERVICE_SPEC` — ARCHITECTURE 阶段的服务契约（v5.6.0 BaaS 接入锚点）
  - `data_persistence` 四值：none/embedded/external/supabase（supabase 当前为声明态）
- PHASE_ARTIFACT_MAP：DEVELOPMENT 加 APP_CODE、ARCHITECTURE 加 SERVICE_SPEC（均次要位，primary 不变）
- DELIVERABLE_REQUIRED_FIELDS / ARTIFACT_LABELS / ARTIFACT_SCHEMAS 同步扩展
- REQUIRED_DELIVERABLES 加入 app_code / service_spec

**字段可编辑性策略 (T4):**
- `domain/artifact/policy.py` — EDITABLE_FIELDS 白名单
- 文档类 artifact：整体可编辑；工程产物（APP_CODE/PROTOTYPE）：全只读；SERVICE_SPEC：仅 notes 可改
- `update_content` 加字段校验 + partial 合并模式，不可编辑字段抛 ValueError

**前端编辑能力 (T7):**
- `ArtifactEditor` — JSON 查看/编辑，调 updateArtifact API
- `editable-types.ts` — 镜像后端白名单，工程产物不显示编辑按钮
- `DeliverableDrawer` 集成编辑入口

**部署回滚入口 (T8):**
- 后端 `GET /deployments`、`GET .../deployment/latest`、`POST .../deployments/{id}/rollback`
- 前端 `RollbackButton` — 确认弹窗 + 已回滚禁用态
- `AppCode` / `ServiceSpec` 渲染器（ServiceSpec 对 supabase 声明态显式警告）

### Deferred

- MCP server 骨架（T9/T12）→ v5.6.0 T18/T19

## [5.4.0] - 2026-06-23

### Added — 部署层真实化 + 上下文架构升级

**部署能力 (T1-T9):**
- `domain/deployment` 聚合：Deployment 实体 + 状态机 (pending/building/uploading/deployed/failed/rolled_back)
- `DeployType` 值对象预留 `container`/`serverless`/`baas_app` 未来扩展位
- `infrastructure/deployer/static_site.py` — S3 静态部署后端（对标 XSpace BOSDeployer）
- `application/deployment/service.py` — `DeployService` 编排 build → upload → URL 回写
- `StorageAdapter` 重构：`upload_dir()` 目录全量上传、去硬限、50MB 单文件 + 分片
- DEPLOYMENT 阶段 hook 接入 `DeployService`，Agent 触发 → URL 回写 Version/Project
- 预览 vs 部署存储解耦：`previews/` vs `deployments/`，前者可覆盖后者不可变

**上下文架构升级 (T10-T11):**
- `ContextProvider` Protocol — 统一上下文来源接口（项目/经验/对话历史/ReviewFeedback）
- `ContextAssembler` — 按 token 预算和优先级组装 system prompt
- `PromptBuilder.build_system_prompt()` 委托给 ContextAssembler
- `ReviewFeedback` 作为独立 `ContextSegment` 注入下次对话

### Changed

- `application/pipeline/service.py` 引入 `ProjectContextProvider` 取代硬编码上下文拼接
- `application/context/` 新增模块，下含 `protocol.py` / `assembler.py` / `provider.py` / `providers/`
- `config.py` 新增 `deploy_path_prefix` / `deploy_cdn_domain` / `deploy_max_file_size`
- `.env.example` 对齐 `ARC_DEPLOY_*` 配置项

## [5.3.0]

### Added — 原型预览架构升级

- Version 增加 `prototype_preview_url` 字段，支持 S3 持久化预览
- 新增 `GET /api/projects/{id}/prototype-status` 接口，前端据此控制按钮状态
- `PrototypeBundleService.publish_bundle()` — 版本级原型聚合上传到 S3
- 版本 Release 自动生成不可变 prototype snapshot
- Artifact 产出后自动触发 S3 latest 更新
- 前端预览按钮：空状态置灰 + 版本切换下拉 + 页面数量显示

### Changed

- `prototype-preview` 路由：优先 S3 redirect → 本地文件 → 动态生成 → 友好 HTML 错误页
- `prototype-bundle` 路由新增 `version_id` 过滤参数
- `_auto_persist_prototype` 优先走 S3 发布，本地写入降为 fallback

## [5.2.0] - 2026-06-04

### Changed — 技术债务清理

- `useProjectDetail.ts` 拆分为 4 个 focused hooks（510行→最大190行）
  - `useVersionActions` — 版本 CRUD
  - `useTodoActions` — 需求 CRUD
  - `useVersionAnalysis` — 版本分析 UI 状态
- 补全 17 个单元测试覆盖 v5.1.0 新增功能（provider/service/strategy）

## [5.1.0] - 2026-06-04

### Added — 上下文注入 + 优先级可视化 + AI Changelog

**Prompt 上下文注入改造:**
- 版本分析缓存结果注入 system prompt（AI 对话时了解项目迭代状态）
- 同版本需求来源标记（AI建议 vs 手动创建）
- 对话 greeting 改为上下文感知（基于分析缓存 + 来源 + 描述丰富度动态生成）

**版本发布自动 Changelog:**
- 发布版本时 AI 总结需求列表生成结构化 changelog（按功能分类）
- LLM 失败时自动降级为 bullet list

**需求优先级可视化:**
- TodoList 和 TaskCard 组件展示 P0(红)/P1(橙)/P2(灰) 标签
- 创建需求时支持选择优先级（三选一按钮组，默认 P1）

## [3.8.0] - 2026-06-02

### Added — AI 评审持久化 + 主题模式

**AI 评审三态按钮:**
- 未评审 → "AI 评审"（蓝色）
- 已评审 + 模型未变 → "查看评审 ✅"（绿色），点击弹窗展示结果
- 已评审 + 模型已变 → "查看评审" + "⚠️ 模型已变更"，弹窗内可重新评审
- 评审状态持久化到 useDomainModelReview hook，tab 切换不丢失
- 后端 validate 路由消除重复 LLM 调用（ReviewService 一次搞定）
- ValidationPanel 提取为独立组件（DomainModelTab 520→392 行）

**主题模式:**
- 暗色 / 亮色 / 跟随系统 三种模式
- useTheme hook + localStorage 持久化
- Sidebar 底部主题切换按钮（Moon → Sun → Monitor 循环）
- 亮色变量集完整覆盖所有 CSS 自定义属性

## [3.7.0] - 2026-06-02

### Added — 面板接入端到端联通

- useDomainModelReview hook: 评审反馈 + 历史快照数据管理 (加载/处理/回滚)
- DomainModelTab: 接入 ReviewFeedbackPanel + ModelHistoryPanel，传入 projectId
- 评审反馈面板: 展开详情 + accept/defer/reject 直接操作
- 版本历史面板: 时间线展示 + 一键回滚
- 领域模型升级系统从后端 API → 前端 UI **全链路贯通**

## [3.6.0] - 2026-06-02

### Added — 前端功能贯通

- TodoStatus 加入 `suspended`，STATUS_LABELS + statusBadgeBg 全量更新
- API client 新增 8 个方法: listReviewFeedbacks / resolveReviewFeedback / getDomainModelHistory / rollbackDomainModel / analyzeModelImpact / executeModelUpgrade / resumeSuspendedTodo
- ReviewFeedbackPanel 组件: 评审反馈列表 + 展开详情 + accept/defer/reject 操作
- ModelHistoryPanel 组件: 版本历史时间线 + 回滚按钮
- types/api.ts: +9 新类型 (ReviewFeedback, ImpactReport, UpgradeResult 等)
- TypeScript 零错误, 33 前端测试全绿

## [3.5.0] - 2026-06-02

### Added — 测试收尾：后端 + 前端

- ArtifactService 测试: update/confirm/get_confirmed_context + 边界 (+11 tests)
- DomainModelValidator 测试: 空模型分支覆盖 (+4 tests)
- 前端 Skeleton 组件测试: SkeletonLine/Card/ProjectList/TodoDetail (+4 tests)
- 前端 ActionMenu 组件测试: 空 items/展开/点击/关闭/danger 样式 (+5 tests)
- 前端 MarkdownContent 测试: text/bold/code/link/empty (+5 tests)
- 后端 991→1004, 前端 18→33, **总计 1037 tests**

## [3.4.0] - 2026-06-02

### Added — 核心 Service 测试补齐

- DomainModelExtractor 全部静态方法测试 (+18 tests)
- VersionService 测试: 版本命名/创建/删除/激活/发布 (+15 tests)
- TodoService 测试: 标签提取 + LLM 降级 (+3 tests)
- ExperienceService 测试: confirm/archive/decay (+5 tests)
- ConversationService 测试: format_experiences + prompt 构建 (+5 tests)
- 总测试: 948→991 (+43)

## [3.3.0] - 2026-06-02

### Changed — 功能集成 + 超限拆分

- ReviewService 集成主流程: validate 路由接入闭环, artifact 提取后自动评审
- planning_service.py 拆分: 557→487行, 提取 planning_experience.py
- routes/todo.py 拆分: 557行 → todo/ 目录 (crud + git + conversations + helpers)
- routes/project/core.py 拆分: 513→270行, 提取 scanning.py + github.py
- **非 seeds 超限文件清零** (原 3 个 > 500 行 → 0 个)

## [3.2.0] - 2026-06-01

### Added — 领域模型升级执行机制 (Phase 3/3)

- Todo SUSPENDED 状态: suspend_for_upgrade() / resume_after_upgrade() / is_suspended
- UpgradeStrategy: block (暂停+升级+恢复) / defer (延迟) 策略
- ModelUpgradeOrchestrator: 全流程编排 — 影响分析→暂停高风险→升级模型→标记反馈→恢复低风险
- API: POST /domain-model/upgrade, POST /todos/{id}/resume
- +20 tests (948 total)

## [3.1.0] - 2026-06-01

### Added — 领域模型影响分析 (Phase 2/3)

- RiskLevel 五级风险 + ImpactItem/ImpactReport 值对象
- 21 条风险矩阵规则 (PhaseType × ModelChangeScope → RiskLevel)
- aggregate_extractor: 从交付物提取聚合引用 (4 种识别模式)
- ImpactAnalyzer: 自动分析模型变更对进行中需求的影响
- API: POST /projects/{id}/domain-model/impact-analysis
- +34 tests (928 total)

## [3.0.0] - 2026-06-01

### Added — 领域模型升级基础设施 (Phase 1/3)

- Project.upgrade_domain_model() 快照机制: 变更前自动创建历史版本, 支持 rollback
- ReviewFeedback 领域模块: 实体 + 值对象 + 仓储 + 状态流转 (pending→accepted/deferred/rejected)
- 确定性变更分级器: category × severity → additive/structural/breaking
- ReviewService: Validator 评审结果 → 持久化 ReviewFeedback 闭环
- API: review-feedbacks CRUD + domain-model/history + rollback
- DomainModelExtractor 改用 upgrade_domain_model() 路径
- +63 tests (894 total)

## [2.9.0] - 2026-06-01

### Changed — 架构治理 + 测试补全

- 消除 application 层 8 条循环依赖（2 条顶层 + 6 条延迟 import）
- 补齐 8 个 domain value_objects 单元测试（+206 tests，覆盖率 11%→90%+）
- llm_adapter.py 拆分: 581→3 文件（base + openai_adapter + anthropic_adapter）
- ws/chat.py 拆分: 564→4 文件（chat + connection_manager + ws_helpers + stream_generator）

## [2.6.0] - 2026-06-01

### Added — Agent Git Sync + 全量产品预览

- StreamManager: AI 流式生成与 WS 生命周期解耦，导航离开不丢消息
- 统一消息 ID: streaming message_id 作为 entity UUID，消除重复 key
- 前端 stream_resume: WS 重连自动恢复流式状态
- 工具调用 UI 重构: SerialBatch + ParallelBatch + 自动折叠已完成调用
- 对话模式 TaskCard 删除入口

### Fixed

- 原型预览开发环境打开项目面板 → 改用 Blob URL
- 交付物全完成后 todo 状态自动推进到 done
- 经验列表 500: decisions/pitfalls 兼容 dict 格式
- 经验详情渲染 dict 对象报错
- 扫描状态 tab 切换后丢失
- 交付物面板流式期间不刷新 → 8s 轮询兜底
- 工具调用在"思考中"下方 → 调整到上方

## [2.8.0] - 2026-06-01

### Added — Resilience (长程韧性)
- CheckpointManager 检查点: autopilot 每轮创建状态快照, 支持跨 session 恢复
- HandoffPackage 结构化会话摘要: 目标/完成/待办/决策/失败/文件 六维提炼
- HookManager 7注入点管道: pre_input→post_response, 事件驱动, 失败隔离, 5s 超时
- 6 个模块单元测试补齐 (+38 tests)

### Changed
- SettingsTab.tsx 拆分: 694→568 行, 提取 GitHubSection 独立组件

## [2.7.0] - 2026-06-01

### Added — Intelligence (智能升级)
- MemoryScorer 五维检索打分: relevance(0.4) + recency(0.2) + frequency(0.15) + authority(0.15) + user_explicit(0.1)
- prompt_builder 集成 MemoryScorer: 替代纯 cosine 排序, 按综合分 Top-K 注入
- PR 自动创建 + AI description
- 冲突诊断

## [2.6.0] - 2026-06-01

### Added — Quality Guard (质量守卫)
- VerifyChain 四级验证链: 语法校验 → 语义检查 → 集成检查 → 意图自审
- DriftDetector 漂移检测: 关键词重叠度 + 行为模式检测, 分级响应 (MILD→SEVERE)
- ErrorLoopDetector 死循环检测: 滑动窗口周期模式识别 (周期2/3, LCS相似度)
- ToolRegistry.execute_with_retry: 瞬时错误指数退避重试

## [2.5.0] - 2026-05-31

### Added — Context Engine (上下文引擎)
- ContextController 上下文装配器: token 预算分配, 优先级淘汰 (P0→P3), 缓存友好排序
- CompressionManager 三级压缩: L1 微压缩(规则, <10ms), L2 段落压缩(LLM摘要), L3 全量压缩(重建最小上下文)
- Anthropic Prompt Cache 支持: system 消息添加 cache_control, TTFT 降低 60-85%
- tool_loop L1 压缩: 工具输出 >10K 字符自动 head+tail+摘要
- conversation_strategy.py 拆分: 669行 → prompt_builder.py(217) + execution_engine.py(372) + conversation_strategy.py(284)

### Changed
- conversation_strategy.py 从 669 行拆分为 3 个独立模块
- ContextController 替代 get_context_window(50) 硬编码, 引入 token 预算管理
- ExecutionEngine 传递 CompressionManager + DriftDetector + ErrorLoopDetector 给 ToolAwareLoop
- AnthropicAdapter 4 处 LLM 调用添加 cache_control 标记

## [2.4.0] - 2026-05-31

### Added
- 扫描状态/进度服务端持久化 (scan_status 字段)
- 项目逻辑删除 (deleted_at + restore API)
- Repository 接口补齐 (domain ABC + infrastructure 继承)
- LLM adapter chat_with_tools() 统一接口

### Fixed
- 循环依赖消除 (artifact↔pipeline, conversation↔execution)
- tool_loop 去私有属性访问 (穿透 adapter 封装)
- 文件超限拆分 (6 个提取模块)

## [2.3.0] - 2026-05-30

### Added
- 对话模式 Tool Use 完整链路: ToolRegistry(5工具) + ToolAwareLoop(Anthropic+OpenAI) + SSE 事件广播
- GitHub 连接自动 clone + scan: connect 后自动 clone 到 ~/.arc/repos/, 自动触发扫描
- 扫描状态查询 API: GET /scan-codebase/status
- quick_message_service.py: route 层业务逻辑抽取到 application 层
- 12 个新单元测试 (github_service/quick_message_service)

### Fixed
- 扫描永远卡在"扫描中": SSE 订阅竞态条件 — subscribe() 检查 is_running + 300s 超时
- 扫描闪退: SSE 空订阅时重查 DB 拿最新结果 + 错误透传
- scanner_analysis.py import 错误: get_settings → settings 单例
- ToolAwareLoop 缺少 metrics 属性导致 AttributeError
- 前端 close 事件闭包过期 + SSE 5min 超时保护

### Changed
- backend/.env.example 补齐 config.py 对应的 17 个缺失字段
- k8s/secrets.yml → secrets.example.yml (防误填真实密钥)
- k8s/configmap.yml 补充 ARC_DB_POOL_RECYCLE
- routes/todo.py 精简 68 行 (逻辑移入 service)
- routes/project/core.py clone 逻辑从 route 移入 github_service

## [2.2.0] - 2026-05-27

### Added
- 交付物抽屉挤压式布局 — flex inline 面板 + 拖拽调宽 (320-720px), 对话区可持续沟通
- domain 层单元测试 48 cases (planning entity/project entity/user entity)
- application 层单元测试 44 cases (context_provider/artifact_extractor/conversation_strategy/planning_service/quota_service/scanner/scan_task)
- k8s kustomization.yml images transformer, 镜像名参数化

### Changed
- seeds/data.py 2344→1117 行, 拆出 data_artifacts.py + data_messages.py
- seeds/gateway.py 1565→591 行, 拆出 gateway_artifacts.py + gateway_messages.py
- frontend api/client.ts 834 行单文件拆为 client/ 目录 6 模块 (函数式组合模式)
- k8s deployment 镜像从硬编码 ghcr.io 改为 kustomize placeholder 模式

### Removed
- 死代码 openhands_executor.py (无引用)
- 冗余依赖 passlib (未使用)

## [2.1.0] - 2026-05-27

### Added
- DDD 三阶段自主建模 prompt (战略设计→事件风暴→战术建模, AI 自主驱动无需人工干预)
- event_storming schema 适配 (tech_architecture 新增 events/commands 字段)
- DomainModelExtractor 事件风暴数据提取 (events→聚合.events, commands→聚合.methods)
- LLM 驱动领域模型质量评审 (domain_model_validator.py, 四维度评审 + score/issues/strengths)
- POST /projects/{id}/domain-model/validate 端点
- DomainModelTab AI 评审按钮 + ValidationPanel 弹窗 (按 severity 分色展示)
- ArtifactRepository.list_by_todo_ids() 批量查询方法
- alembic migration: nullable 对齐 + 索引规范化 (7d587912c43d)

### Fixed
- 依赖关系图空状态 — 聚合无子域/上下文时从 .context 字段 fallback 分组
- 领域模型刷新重复合并误报 — deepcopy 快照比较确保幂等
- ruff lint 全量清理 54→0 (F401/I001/E741/N817/E501)

### Changed
- DDD_TDD_GUIDANCE 动态注入战略/战术上下文 (子域+上下文+关系+聚合详情)
- domain model refresh N+1 查询优化 (IN 查询替换逐条查询)
- build_ddd_tdd_section() 重写为完整战略/战术上下文生成
- ruff per-file E501 ignore 配置 (publish_service.py, prompts.py)

## [2.0.0] - 2026-05-26

### Added
- 多租户隔离架构 (Organization domain + membership + org-scoped 查询)
- Free/Pro/Team 三级定价模型 (QuotaService + UsageDaily + 前端用量展示)
- GitHub 集成 (Issue↔Todo 双向同步, Webhook HMAC-SHA256 验证, 前端连接 UI)
- 云端部署方案 (docker-compose.prod.yml, K8s manifests, GHCR CI/CD)
- project.py 路由拆分为子模块 (8 文件, 每文件 ≤300 行)
- Frontend nginx.conf (gzip + API/WS 反向代理 + SPA 路由)
- 前端 403 配额拦截 + quotaEvents 事件总线 + Toast warning 类型
- WebSocket quota_exceeded 实时配额通知

### Changed
- Frontend Dockerfile 改用外部 nginx.conf 配置

## [1.2.0] - 2026-05-25

### Added
- AgentLoop 生产级引擎 — finish_reason 续写/交付物验证重试/预算超时
- AgentLoop 目标驱动改造 + AutoPilot 自驾模式 (最大12轮)
- 交付物拆分为8环节 (交互设计/视觉规范/原型设计独立)
- DDD+TDD 方法论条件注入 (conversation_strategy)
- 项目级领域模型视图 (DomainModelTab 战略战术可视化)
- DDD 战略设计注入 tech_architecture schema (domain_design 字段)
- 原型产品预览 (Blob URL + S3 持久化发布)
- S3+BaaS 存储层统一 (StorageAdapter: upload/download/delete/delete_prefix)
- JWT refresh token 吊销机制 (jti + DB blacklist)
- SSE 自动重连 + 心跳检测 (max 5 retries, exponential backoff)
- ChatMessages 虚拟列表 (@tanstack/react-virtual, 80+ 消息阈值)
- Artifact content discriminated union 类型定义 (10 个 content interface)
- 核心模块单元测试 (storage/publish/document/version service, 36 cases)
- WebSocket IDOR 防护 (资源所有权验证)
- 路径遍历防护 (storage key + filename sanitization)
- CSP meta 注入 (已发布原型 connect-src 'none')
- FK 列索引优化 (11 个高频外键列)

### Fixed
- 交付物状态不一致 (regex/JSON解析/race condition 三层修复)
- 前端 AbortError 处理 (SSE/fetch 取消不再弹错误 Toast)
- auth test 适配 create_refresh_token 返回 tuple
- PWA Workbox 缓存规则限制 method: 'GET'
- Blob URL 内存泄漏 (60s 后自动 revokeObjectURL)

### Changed
- 内存分页全部改为 SQL 分页 (version/experience/document/planning repos)
- Experience 状态转换收口到 ExperienceService (confirm/archive/promote/feedback)
- Version 创建/删除收口到 VersionService
- useProjectDetail God Hook 拆分 (useExperiences + useDomainModel)
- DocumentService 统一走 StorageAdapter (不再依赖本地文件系统)

## [1.1.0] - 2026-05-25

### Added
- auth service 单元测试 — 覆盖注册/登录/token刷新/密码校验
- route 冒烟测试 — 全路由 404/401 基本响应验证

### Fixed
- todo.py get_dependencies 缺失路由装饰器
- 前端静默 .catch(() => {}) 错误处理改为 Toast 通知
- 硬编码 localhost 统一走环境变量

### Changed
- 所有列表 API 统一支持 page/page_size 分页参数
- Docker 密码外部化, 通过 .env 注入
- TodoDetail.tsx 拆分为 pages/todo/ 下独立子组件

## [1.0.0] - 2026-05-21

### Added
- 角色权限体系 — UserRole 枚举（admin/member/viewer），User model 扩展 role 字段
- 项目成员管理 — 成员邀请/移除/角色变更 API，创建项目自动添加创建者为 admin
- 权限中间件 — require_project_role 依赖注入，成员管理写操作需 admin 权限
- 项目成员前端 — MembersTab 组件（成员列表、添加、角色变更、移除）
- 前端权限渲染 — 根据项目角色控制操作按钮显隐（viewer 只读、member 可操作、admin 可管理）
- 经验访问控制 — 项目经验团队成员可见，个人经验仅创建者可见，搜索范围限定
- 团队经验复用 — 成员间经验发现，经验库 scope 筛选（个人/项目）

### Changed
- 项目列表查询扩展 — 用户可见自己创建的项目 + 作为成员参与的项目
- 登录/注册返回用户 role 字段
- /me 端点返回 role 字段

## [0.5.0] - 2026-05-21

### Added
- 经验衰减机制 — confidence 按半衰期（默认 180 天）自动衰减，过期标记（is_stale）
- 经验提炼 — 项目经验一键提炼为个人经验（AI 去项目细节 + source_experience_id 关联追踪）
- 经验编辑增强 — 支持编辑 category、source、tags、half_life_days
- 复用效果追踪 — 按类别聚合分析 API、过期统计、top 复用经验
- 定时衰减任务 — 后端 lifespan 注册 24h 批量衰减循环
- 前端过期标记 — 经验列表/详情/项目经验 Tab 均显示"过期"标记
- 提炼按钮 — ExperienceDetailModal 和 ExperiencesTab 新增"提炼"操作
- 经验库过期统计 — ExperienceList 页面头部显示过期经验数

### Removed
- 项目仪表盘 Tab — 移除 DashboardTab 及关联后端 API（功能价值不足）

## [0.4.0] - 2026-05-21

### Added
- Claude Code 适配器 — 通过 subprocess 驱动 `claude` CLI 执行开发任务
- Codex 适配器 — 通过 OpenAI Responses API 集成 Codex 代码执行
- 需求依赖关系系统 — todo_dependencies 表、依赖 CRUD API、前端阻塞状态展示
- 项目仪表盘 — 需求统计、版本进度、Agent 执行情况、最近活动聚合 API + 前端页面
- 同版本需求感知 — AI 对话和 Agent 执行时自动注入同版本其他需求上下文
- Agent 集成测试 — Claude Code 适配器全链路测试（启动/状态/事件/取消）
- 版本管理与跨会话上下文注入体系（docs/versions/ + CLAUDE.md 协议）

### Changed
- DB 索引优化 migration 幂等化
- TodosTab/TodoSidebar 交互优化（未读指示、状态展示）

## [0.3.0] - 2026-05-21

### Added
- 代码库扫描与 AI 总结（后端异步任务 + SSE 流式推送）
- 规划引擎（PlanningService + DocumentService）
- 执行模式升级（Pipeline / Conversation 双模式）
- 经验系统升级（scope/category/source/confidence）
- PWA 支持（Workbox + Service Worker、离线缓存、安装到主屏幕）
- WS Token 自动续期

### Fixed
- 蓝点未读修复 — mark_seen 用 func.now() 统一时间源

## [0.2.0] - 2026-05-18

### Added
- 用户认证体系（手机号 + 密码登录、JWT Token）
- Pipeline 门禁校验
- Mermaid 流程图渲染

## [0.1.0] - 2026-05-17

### Added
- 项目管理体系（Project / Version CRUD）
- 响应式 UI 布局
- 种子数据系统
- 经验库完善

## [0.0.1] - 2026-05-16

### Added
- Arc v1 MVP — AI 驱动的待办工作台初始版本
- 统一 Coding Agent 编排层（OpenHands / Codex / Claude Code / Cursor）
- Todo 全生命周期管理
- 7 阶段 Pipeline（需求澄清 → 经验沉淀）
- AI 对话（多模型支持）
- 经验库（向量搜索）

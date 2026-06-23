# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

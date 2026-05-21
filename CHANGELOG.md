# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

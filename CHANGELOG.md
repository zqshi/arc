# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- API 限流中间件（IP 滑动窗口，全局 120 req/min，LLM 接口 20 req/min）
- 列表接口分页支持（todo、experience）
- 前端测试基础设施（Vitest + Testing Library）
- 前端 Token 主动刷新（过期前 2 分钟自动续期）
- `CONTRIBUTING.md` 文档对齐规范
- CI `docs-freshness` 文档新鲜度检查
- `.env.example` 全量配置注释

### Changed
- Mermaid 改为动态加载，主 bundle 减小 ~800KB
- Backend Dockerfile 改为多阶段构建，以非 root 用户运行
- 数据库连接池显式配置（pool_size=10, max_overflow=20, pool_recycle=3600）
- CORS 默认为空列表，仅 DEBUG 模式自动追加 localhost

### Fixed
- JWT Secret 空值时生产模式启动报错（消除不安全 fallback）
- 种子账号仅 DEBUG 模式注入（生产不再暴露 demo/test 账号）
- SMS 验证码增加速率限制（60s 间隔、1h 5 次上限、连续失败锁定）

### Security
- P0: 消除 JWT 硬编码 fallback secret
- P0: 生产模式禁止自动创建种子账号
- P0: SMS 验证码防暴力枚举（速率限制 + 失败锁定）
- P0: CORS 生产模式不再默认开放 localhost
- P2: Backend 容器以非 root 用户运行
- P2: API 全局限流防 DDoS

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

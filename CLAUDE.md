# Arc 项目开发规范

## 上下文加载协议

**每次新会话开始开发任务前, 必须执行以下步骤:**

1. 读取 `docs/versions/` 目录下以 `-current.md` 结尾的文件(有且只有一个), 了解当前版本的目标、范围、约束和进行中的任务
2. 检查当前版本的**任务依赖表**, 确认要做的工作没有被 blocked
3. 如果用户要求做的功能不在当前版本范围内, 主动提示并建议查看 `-next.md` 或 `backlog.md`

**版本文件命名规则:**
- `vX.Y.Z-current.md` — 当前活跃版本(有且仅有一个)
- `vX.Y.Z-next.md` — 下一版本规划(当前版本完成后升级为 current)
- `vX.Y.Z-snapshot.md` — 已完成版本的决策存档

## 依赖检查与任务编排规则

当用户提出开发需求时, 按以下流程处理:

### 1. 任务定位
- 在 current.md 的任务依赖表中查找该任务
- 如果该任务不在表中, 评估它是否属于当前版本范围
- 不属于当前版本 → 提醒用户, 建议查看 backlog.md 或将其加入当前版本

### 2. 依赖检查
- 如果任务状态为 `blocked`, 列出未完成的前置依赖, 建议执行顺序
- 如果前置依赖可以快速完成(< 30min), 建议在同一会话内先完成前置再做目标任务
- 如果前置依赖工作量大, 建议先完成前置任务再开新会话

### 3. 并行任务识别
- 检查依赖图中是否有可并行的任务(互不依赖且都处于 pending 状态)
- 如果用户一次会话有余力, 主动建议并行任务: "T1和T3互不依赖, 可以在本次会话一起完成"
- 标注关键路径上的任务, 优先推进关键路径

### 4. 任务完成后更新
- 完成一个任务后, 立即更新 current.md 中该任务状态为 `done`
- 检查是否有因此解除 blocked 的下游任务, 将其状态从 `blocked` 改为 `pending`
- 如果所有任务完成, 提醒用户可以执行版本切换

### 5. 计划外工作处理
- 如果开发过程中发现需要新增任务(比如发现一个前置bug), 将其加入 current.md 的任务表
- 给新任务分配 ID (在现有最大ID基础上递增)
- 评估新任务是否影响其他任务的依赖关系, 更新依赖图

## 版本切换协议

当一个版本的所有任务完成时:
1. 将 `vX.Y.Z-current.md` 精简为 snapshot 格式(删除执行细节, 只保留目标/交付/决策/遗留/约束)
2. 重命名为 `vX.Y.Z-snapshot.md`
3. 将 `vNext-next.md` 重命名为 `vNext-current.md` (激活下一版本)
4. 如果不存在 next.md, 从 `backlog.md` 中取出下一个版本规划, 基于 `TEMPLATE.md` 创建
5. 更新 `CHANGELOG.md` 和 `backlog.md`(移除已启动的版本)
6. 为再下一个版本创建 `vX.Y.Z-next.md` (可选, 有规划时提前建)

## 技术规范

### 后端 (Python + FastAPI)
- 架构: DDD 分层 — domain / application / infrastructure / interface
- domain 层不允许依赖 infrastructure
- 新 API 路由必须挂载 auth 依赖
- 列表 API 必须支持分页 (skip/limit)
- 数据库变更必须有 alembic migration
- 新表必须添加必要索引

### 前端 (React + TypeScript + Vite)
- 状态管理以服务端为主, 前端轻量
- 新页面必须支持 PWA 离线降级
- 测试框架: Vitest + Testing Library

### 通用
- commit message 格式: `type: 中文描述` (feat/fix/refactor/docs/test/chore)
- 不引入新的外部依赖前先评估是否必要
- API 响应格式保持一致, 错误用 HTTPException

## 关键文档索引

| 文档 | 用途 | 何时读 |
|------|------|--------|
| `docs/versions/*-current.md` | 当前版本上下文 | 每次会话开始 |
| `docs/versions/backlog.md` | 后续版本规划 | 讨论新功能范围时 |
| `docs/PRD-v1.md` | 产品需求定义 | 需要理解产品设计意图时 |
| `docs/arc-product-vision.md` | 产品全景与定位 | 需要理解商业逻辑时 |
| `docs/arc-module-breakdown.md` | 模块拆解与实施计划 | 需要理解模块边界和接口时 |
| `docs/agent-upgrade-plan.md` | Agent适配器计划 | 开发Agent相关功能时 |
| `CHANGELOG.md` | 版本变更记录 | 发版时 |

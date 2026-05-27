# 贡献指南 — 文档与代码对齐规范

## 核心原则

**代码是唯一真相源 (Single Source of Truth)**

所有文档、脚本、配置必须从代码推导，不允许文档"自说自话"。当文档与代码冲突时，以代码为准并修复文档。

---

## 文档分类与对齐规则

### 1. 自动生成类 — 不手写

| 文档 | 生成方式 | 规则 |
|------|---------|------|
| API 接口文档 | FastAPI `/docs` 自动生成 | 不手写 OpenAPI spec，通过 Pydantic schema 驱动 |
| 前端类型定义 | `frontend/src/types/api.ts` | 必须与后端 schema 字段对齐 |

### 2. 设计态文档 — 允许超前

位置：`docs/` 目录

设计态文档（PRD、产品愿景、模块拆解）允许超前于代码实现，但 **必须标注实现状态**：

- `[IMPLEMENTED]` — 已在代码中实现
- `[PLANNED]` — 尚未实现，属于规划中
- `[DEPRECATED]` — 设计已废弃，代码已移除或方向已变

### 3. 实现态文档 — 必须与代码同步

| 文档 | 对齐对象 |
|------|---------|
| `README.md` | 项目结构、启动方式、环境要求 |
| `CHANGELOG.md` | 每次发版的变更记录 |
| `.env.example` | `backend/src/arc/config.py` 中所有 Settings 字段 |
| `docker-compose.yml` 注释 | 实际服务配置 |
| `backend/Dockerfile` | 实际构建流程 |

---

## 更新时机 — PR 必检清单

**任何 PR 合并前，作者必须自查以下规则：**

### 后端代码变动

| 变动路径 | 必须同步更新 |
|---------|-------------|
| `backend/src/arc/domain/` | `docs/arc-module-breakdown.md` 对应模块标注 |
| `backend/src/arc/interface/routes/` | `README.md` 如涉及新 API 模块 |
| `backend/src/arc/config.py` 新增字段 | `.env.example` 添加对应变量和注释 |
| `pyproject.toml` 依赖变动 | `README.md` 前置要求章节 |

### 前端代码变动

| 变动路径 | 必须同步更新 |
|---------|-------------|
| `frontend/src/types/api.ts` | 与后端 schema 字段名/类型完全对齐 |
| `frontend/package.json` 依赖变动 | `README.md` 前置要求章节 |

### 基础设施变动

| 变动路径 | 必须同步更新 |
|---------|-------------|
| `docker-compose.yml` | `README.md` 快速启动章节 |
| `backend/Dockerfile` 或 `frontend/Dockerfile` | `README.md` 部署章节 |
| `.github/workflows/` | `README.md` 如涉及新的 CI 步骤 |

### 发版

| 事件 | 必须操作 |
|------|---------|
| 合并到 main 的功能性变更 | 更新 `CHANGELOG.md` Unreleased 区域 |
| 正式发版（tag） | 将 Unreleased 改为版本号 + 日期 |

---

## 脚本对齐规则

| 脚本 | 对齐对象 | 规则 |
|------|---------|------|
| `backend/src/arc/seeds/` | `backend/src/arc/domain/` 各实体字段 | 种子数据的字段必须与 domain entity 完全对齐，新增/删除字段时同步修改 |
| `backend/alembic/versions/` | `backend/src/arc/infrastructure/models/` | 新 migration 必须通过 `alembic revision --autogenerate` 生成，手写需注明原因 |

---

## CI 自动检查

CI 流水线包含 `docs-freshness` 检查（仅警告不阻塞），当检测到以下情况会发出 warning：

- 修改了 `domain/`、`routes/`、`config.py` 但未修改任何文档文件
- 修改了 `docker-compose.yml` 或 `Dockerfile` 但未修改 `README.md`
- 修改了 `config.py` 新增 Settings 字段但 `.env.example` 未更新

---

## 文档质量标准

1. **无孤立文档**：每份文档必须从 README 或 docs/ 目录可达
2. **无过期截图**：如有 UI 截图，必须在 UI 变更时同步更新或删除
3. **无硬编码路径**：文档中引用的文件路径必须实际存在
4. **无重复内容**：同一信息只在一处维护，其他位置通过链接引用

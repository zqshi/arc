# Arc

> 让研发不再只靠人记、人追、人补，而是让 AI 真正参与到每一步交付中。

Arc 是一套面向研发团队的 AI 驱动待办工作台。  
它不只是"帮你管任务"，而是把**需求澄清、方案设计、代码编写、质量把关、经验沉淀**串成一条由 AI 全程参与的研发链路。

很多团队用了项目管理工具，依然卡在同样的地方：

- 需求拆了一堆 ticket，但没人帮你想清楚"到底做什么"
- 代码写完了，但为什么这么做、踩过什么坑，没有地方沉淀
- Agent 工具很多，但接入后不知道怎么编排进真实研发流程
- 经验全靠老员工口传，换人就回到起点

## 一句话理解

Arc 把"待办管理"升级为"AI 参与的研发推进系统"，让每一条需求从创建到交付，都有 AI 辅助思考、编排执行、积累经验。

## 它为什么值得看

- 它不是另一个 Jira / Linear，而是让 AI 真正进入研发决策环节
- 它不是只调一个大模型聊天，而是支持多 Agent 协作（OpenHands / Codex / Claude Code / Cursor）
- 它不是一次性生成，而是七阶段 Pipeline 逐步推进、每步有门禁
- 它不是黑盒 AI 演示，而是可以进入团队日常工作的工程化系统

## 你会立刻感受到什么

- 从"写 ticket"到"AI 帮你把需求想清楚"明显更快
- 从"手动分配"到"AI 自动编排 Agent 执行"明显更省
- 从"每次都重新踩坑"到"经验自动沉淀和复用"明显更稳
- 从"接入一个 AI 就结束"到"多模型多 Agent 灵活调度"明显更实用

## 产品价值

### 1. 需求即研发起点，不再停留在文字描述

Arc 用结构化 Pipeline 承接每一条待办，把模糊需求逐步转化为分析报告、技术方案、可执行代码，而不是让需求在看板里排队等人处理。

### 2. 多 Agent 编排，不只是调用一个模型

从 OpenHands 到 Claude Code，从 Codex 到 Cursor，Arc 用 Registry + Adapter 模式统一接入多种编码 Agent，按需求类型和复杂度自动分发任务。

### 3. 七阶段 Pipeline，每步有门禁

需求分析 → 方案设计 → 代码生成 → 代码审查 → 测试验证 → 部署上线 → 经验沉淀。  
每个阶段有明确的产出物和推进条件，不会跳步、不会失控。

### 4. 经验会沉淀，而不是做完就忘

每次研发过程中的决策、踩坑、解法，系统自动提炼为经验条目。下次遇到相似问题，AI 会主动调取相关经验，避免团队反复踩同一个坑。

## 典型使用场景

- 需求澄清：把模糊的一句话需求，转化为结构化的分析报告
- 方案设计：AI 辅助生成技术方案，支持多方案对比
- 代码编排：自动选择合适的 Agent 完成编码任务
- 质量把关：Pipeline 门禁确保每步产出物达标才能推进
- 经验复用：向量搜索相似经验，新成员也能继承团队积累

## Arc 的工作方式

```text
需求输入（创建待办）
   ↓
AI 辅助需求分析与结构化拆解
   ↓
技术方案生成（多方案对比）
   ↓
Agent 自动编排执行（OpenHands / Codex / Claude Code）
   ↓
Pipeline 七阶段逐步推进
   ↓
经验自动提炼与沉淀
   ↓
下次需求 → 相似经验自动召回
```

## 适合谁

- 技术负责人：让 AI 真正参与研发流程，不再只是聊天框
- 研发团队：从接需求到交付，每步都有 AI 辅助思考和执行
- AI 产品团队：把多种 Agent 能力编排进真实业务流程
- 创业团队：用最小人力完成更大交付量，经验不随人走

## 当前已落地能力

- 用户认证（账号密码 + 短信验证码）
- 项目管理（多项目、版本管理、激活/发布流程）
- 待办全生命周期管理（创建、推进、完成、归档）
- 七阶段 Pipeline 引擎（含门禁校验）
- 多 Agent 接入与编排（OpenHands / Codex / Claude Code / Cursor）
- 多模型 AI 适配（Anthropic / OpenAI / DeepSeek）+ 韧性层
- 经验库（自动提炼、向量搜索、相似度召回）
- 实时对话（WebSocket）
- API 限流、JWT 双令牌、SMS 防刷
- Docker 一键部署（多阶段构建、非 root 运行）

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | Python 3.12 · FastAPI · SQLAlchemy (async) · DDD 四层架构 |
| 数据 | PostgreSQL 16 (pgvector) · Alembic Migration |
| 前端 | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4 |
| AI | Anthropic · OpenAI · DeepSeek（多模型动态切换） |
| Agent | OpenHands · Codex · Claude Code · Cursor（Registry + Adapter） |
| 部署 | Docker Compose · 多阶段 Dockerfile · 非 root 运行 |

## 快速开始

环境要求：

- Docker & Docker Compose
- Node.js >= 22（前端开发）
- Python 3.12（后端开发）

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd arc
```

### 2. 环境配置

```bash
cp .env.example .env
# 编辑 .env，至少填写一个 LLM API Key
# 生产环境必须设置 ARC_JWT_SECRET（openssl rand -hex 32）
```

### 3. Docker 一键启动

```bash
docker compose up -d
```

服务地址：

- 前端：http://localhost:3001
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 4. 本地开发

**后端：**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose up db -d
alembic upgrade head
ARC_DEBUG=true uvicorn arc.main:app --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

DEBUG 模式自动创建种子账号：demo/demo123、test/test123

## 开发配置说明

核心环境文件：`.env.example`（与 `backend/src/arc/config.py` 一一对应）

当前默认开发策略：

- 所有配置项以 `ARC_` 为前缀
- `ARC_DEBUG=true` 开启调试模式 + 种子账号
- `ARC_SMS_MOCK_MODE=true` 短信验证码固定为 `666666`
- `ARC_DATABASE_URL` 必须指向带 pgvector 扩展的 PostgreSQL

## 上线前必须修改的配置

### 1. 安全相关

```bash
ARC_JWT_SECRET=<openssl rand -hex 32>   # 必须设置，否则拒绝启动
ARC_DEBUG=false                         # 关闭调试模式
ARC_CORS_ORIGINS=https://your-domain    # 限定允许的前端域名
```

### 2. 数据库

```bash
ARC_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/arc
# 连接池默认：pool_size=10, max_overflow=20, pool_recycle=3600
```

### 3. AI 服务

```bash
# 至少配置一个
ARC_ANTHROPIC_API_KEY=sk-ant-...
ARC_OPENAI_API_KEY=sk-...
ARC_DEEPSEEK_API_KEY=sk-...
```

### 4. 短信服务

生产环境不要使用 `ARC_SMS_MOCK_MODE=true`，配置真实短信服务。

## 安全特性

- JWT access + refresh token 双令牌认证
- 密码 bcrypt 哈希存储
- SMS 验证码速率限制（60s 间隔、1h 5 次上限、连续失败锁定）
- API 全局限流（IP 滑动窗口，默认 120 req/min）
- 生产模式强制 JWT Secret 配置（未设置直接拒绝启动）
- Docker 容器非 root 运行
- CORS 生产默认为空，必须显式配置

## 常用命令

```bash
# 全栈启动
docker compose up -d

# 后端开发
ARC_DEBUG=true uvicorn arc.main:app --reload

# 前端开发
cd frontend && npm run dev

# 后端测试
cd backend && pytest -x

# 前端测试
cd frontend && npm test

# 代码检查
cd backend && ruff check src/

# 数据库迁移
cd backend && alembic upgrade head
```

## 项目结构

```text
arc/
├── backend/
│   └── src/arc/
│       ├── domain/              # 领域层（实体、值对象、仓库接口）
│       ├── application/         # 应用层
│       │   ├── agent/           #   多 Agent 编排（Registry + Adapter）
│       │   ├── ai/              #   LLM 适配器 + 韧性层
│       │   ├── auth/            #   认证（JWT + SMS + 速率限制）
│       │   ├── pipeline/        #   七阶段 Pipeline 服务
│       │   └── experience/      #   经验库服务（向量搜索）
│       ├── infrastructure/      # 基础设施层（ORM、仓库实现、连接池）
│       └── interface/           # 接口层
│           ├── routes/          #   REST API（分页）
│           ├── ws/              #   WebSocket（对话）
│           ├── schemas/         #   请求/响应 Schema
│           └── middleware/      #   中间件（API 限流）
├── frontend/
│   └── src/
│       ├── api/                 # API 客户端（Token 主动刷新）
│       ├── components/          # UI 组件 + Artifact 渲染器
│       ├── contexts/            # React Context
│       ├── hooks/               # 自定义 Hooks
│       └── pages/               # 页面
├── docs/                        # 设计态文档
├── docker-compose.yml           # 4 服务编排
├── CONTRIBUTING.md              # 文档对齐规范
├── CHANGELOG.md                 # 变更日志
└── .env.example                 # 环境变量模板
```

## 文档导航

- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 贡献规范：[CONTRIBUTING.md](./CONTRIBUTING.md)
- 模块拆解：[docs/arc-module-breakdown.md](./docs/arc-module-breakdown.md)
- 环境变量：[.env.example](./.env.example)
- API 文档：启动后访问 http://localhost:8000/docs

## 许可

Private — All rights reserved.

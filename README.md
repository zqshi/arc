# Arc — AI 驱动的研发工作台

Arc 是面向研发团队的智能待办工作台，通过 AI 辅助完成需求分析、方案设计、代码编写等研发全流程。

## 技术栈

- **后端**: Python 3.12 · FastAPI · SQLAlchemy(async) · PostgreSQL 16 (pgvector) · DDD 四层架构
- **前端**: React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4 · Vitest
- **AI**: 多模型支持（Anthropic / OpenAI / DeepSeek）
- **编码 Agent**: 多 Agent 适配（OpenHands / Codex / Claude Code / Cursor）
- **部署**: Docker Compose（多阶段构建，非 root 运行）

## 快速启动

### 前置要求

- Docker & Docker Compose
- Node.js >= 22（前端开发）
- Python 3.12（后端开发）

### Docker 一键启动

```bash
cp .env.example .env
# 编辑 .env 填写必要配置（至少填写一个 LLM API Key）
# 生产环境必须设置 ARC_JWT_SECRET（openssl rand -hex 32）
docker compose up -d
```

服务地址：
- 前端: http://localhost:3001
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

### 本地开发

**后端：**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# 启动 PostgreSQL（需要 pgvector 扩展）
docker compose up db -d
alembic upgrade head
ARC_DEBUG=true uvicorn arc.main:app --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
npm test          # 运行测试
```

## 认证

支持两种登录方式：
1. 账号 + 密码
2. 手机号 + 短信验证码（`ARC_SMS_MOCK_MODE=true` 时固定验证码 `666666`）

DEBUG 模式自动创建种子账号（demo/demo123、test/test123），生产模式不注入。

## 项目结构

```
arc/
├── backend/
│   └── src/arc/
│       ├── domain/              # 领域层（实体、值对象、仓库接口）
│       ├── application/         # 应用层（服务、Agent 编排、AI 适配器）
│       │   ├── agent/           #   多 Agent 编排（registry + adapter 模式）
│       │   ├── ai/              #   LLM 适配器（OpenAI/Anthropic/DeepSeek）+ 韧性层
│       │   ├── auth/            #   认证（JWT + SMS）
│       │   ├── pipeline/        #   7 阶段 Pipeline 服务
│       │   └── experience/      #   经验库服务（向量搜索）
│       ├── infrastructure/      # 基础设施层（ORM 模型、仓库实现、数据库）
│       └── interface/           # 接口层
│           ├── routes/          #   REST API 路由
│           ├── ws/              #   WebSocket（对话）
│           ├── schemas/         #   请求/响应 Schema
│           └── middleware/      #   中间件（限流）
├── frontend/
│   └── src/
│       ├── api/                 # API 客户端（自动 Token 刷新）
│       ├── components/          # 通用组件 + Artifact 渲染器
│       ├── contexts/            # React Context（Auth、CurrentProject）
│       ├── hooks/               # 自定义 Hooks
│       ├── pages/               # 页面组件
│       └── types/               # TypeScript 类型定义
├── docs/                        # 设计态文档（PRD、产品愿景、模块拆解）
├── docker-compose.yml           # 4 服务：DB + Backend + Frontend + OpenHands
├── CONTRIBUTING.md              # 文档对齐规范
├── CHANGELOG.md                 # 变更日志
└── .env.example                 # 环境变量模板（与 config.py 一一对应）
```

## 安全特性

- JWT access + refresh token 双令牌认证
- 密码 bcrypt 哈希存储
- SMS 验证码速率限制（60s 间隔、1h 5 次上限、连续失败锁定）
- API 全局限流（IP 滑动窗口）
- 生产模式强制 JWT Secret 配置
- Docker 容器非 root 运行

## 环境变量

参见 [.env.example](.env.example) 获取完整配置项说明。
变量与 `backend/src/arc/config.py` Settings 类字段一一对应，所有变量以 `ARC_` 为前缀。

## 贡献

参见 [CONTRIBUTING.md](CONTRIBUTING.md) 了解文档对齐规范和 PR 提交要求。

## License

Private — All rights reserved.

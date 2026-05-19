# Arc — AI 驱动的研发工作台

Arc 是面向研发团队的智能待办工作台，通过 AI 辅助完成需求分析、方案设计、代码编写等研发全流程。

## 技术栈

- **后端**: Python 3.12 · FastAPI · SQLAlchemy · PostgreSQL (pgvector) · DDD 架构
- **前端**: React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4
- **AI**: 多模型支持（Anthropic / OpenAI / DeepSeek）
- **编码 Agent**: OpenHands 集成

## 快速启动

### 前置要求

- Docker & Docker Compose
- Node.js >= 20（仅前端开发时需要）
- Python 3.12（仅后端开发时需要）

### Docker 一键启动

```bash
cp .env.example .env
# 编辑 .env 填写必要配置（至少填写一个 LLM API Key 和 ARC_JWT_SECRET）
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
pip install -e ".[dev]"
alembic upgrade head
uvicorn arc.main:app --reload
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

## 认证

支持两种登录方式：
1. 账号 + 密码
2. 手机号 + 短信验证码（开发模式固定验证码 `666666`）

首次使用需注册账号。每个用户的数据相互隔离。

## 项目结构

```
arc/
├── backend/
│   └── src/arc/
│       ├── domain/          # 领域层（实体、值对象）
│       ├── application/     # 应用层（服务、用例）
│       ├── infrastructure/  # 基础设施层（数据库、外部服务）
│       └── interface/       # 接口层（路由、WebSocket）
├── frontend/
│   └── src/
│       ├── api/             # API 客户端
│       ├── components/      # 通用组件
│       ├── contexts/        # React Context
│       ├── hooks/           # 自定义 Hooks
│       └── pages/           # 页面组件
└── docker-compose.yml
```

## 环境变量

参见 [.env.example](.env.example) 获取完整配置项说明。

## License

Private — All rights reserved.

# Arc

> 你做过的每个项目，都在让下一个项目更快更好。

Arc 是一套 AI 原生的项目交付引擎。  
它不是帮你"管项目"，而是把**需求澄清、方案设计、开发执行、质量把关、经验沉淀**串成一条上下文不断裂的交付链路——做完的事不会蒸发，踩过的坑不会重来。

## 它解决什么问题

AI 工具已经很多了。Cursor 帮你写代码，ChatGPT 帮你分析需求，v0 帮你出原型。  
但你有没有发现，**它们之间是断的**：

- 你在 ChatGPT 里花了半小时想清楚的需求，切到 Cursor 要从头描述一遍
- 代码写完了，为什么选了方案 A 不选方案 B，没有任何地方记录
- 上个项目踩过的坑，这个项目又踩了一遍——经验全在脑子里，换人就归零
- 每个 AI 工具都是"用完即弃"，不知道你在做什么项目、到了什么阶段、之前做了什么决策

问题不在于单个环节不够快，而在于**环节之间根本不通**。

Arc 要建的，就是这条被忽视的高速公路。

## 一句话理解

Arc = 项目交付的"上下文高速公路" + 跨项目的"经验资产银行"。  
获客靠前者（立竿见影的效率提升），留存靠后者（越用越值钱的累积资产）。

## 它为什么值得看

- 它不是另一个 Jira / Linear——不做排期、不做人员分配、不做燃尽图
- 它不是另一个 AI 编码工具——不和 Cursor / Claude Code 竞争单点效率
- 它不是无监督的自主 Agent——人在关键节点做决策，AI 在执行层面提效
- 它是**唯一一个让所有环节的 AI 共享同一份项目上下文的系统**

## 你会立刻感受到什么

- 从"每个工具都要重新交代背景"到"AI 始终知道你在做什么" —— **上下文零断裂**
- 从"每个项目都从零开始"到"AI 主动提醒你上次踩过的坑" —— **越用越聪明**
- 从"写完代码才发现需求没想清楚"到"每个阶段有门禁拦截" —— **质量内建**
- 从"客户问为什么这样设计答不上来"到"三秒找到决策依据" —— **交付可追溯**

## 核心价值

### 1. 上下文零断裂 — 获客第一卖点

从需求分析到部署上线，AI 始终持有完整的项目上下文。你在需求阶段和 AI 讨论的所有内容，到了开发阶段 AI 都记得。不需要在工具之间手动搬运信息。

当前没有任何产品做到了这一点。Cursor 不知道你的需求是什么，ChatGPT 不知道你的代码长什么样，Jira 不知道你的技术决策是什么。

### 2. 越用越聪明 — 核心壁垒策略

第一个项目，AI 给你的建议和 ChatGPT 差不多。第五个项目，AI 能直接告诉你"上次你做类似功能时踩过 XXX 的坑，建议这次这样处理"。

经验分两个维度自动积累：
- **个人经验**：跟用户走，跨项目复用。你的技术选型偏好、踩坑记录、最佳实践
- **项目经验**：跟项目走，跨版本复用。架构约束、技术债务、已知问题

经验数据不可迁移，用得越久迁移成本越高。这是一个正向飞轮：经验多 → AI 更准 → 用户更依赖 → 经验更多。

### 3. 质量内建 — 七阶段门禁

每个阶段结束时，系统评估产出物质量——需求里缺少边界条件、技术方案漏了并发处理、测试没有覆盖异常路径。不达标不放行，质量不是事后检查，而是过程保证。

### 4. 交付可追溯 — 从需求到代码的完整链路

任何一行代码都能追溯到需求来源，任何一个决策都能追溯到讨论上下文和经验依据。对于接项目的自由职业者和需要交付文档的团队，这是实实在在的交付价值。

## Arc 的工作方式

```
项目 → 版本 → 需求（三层结构，仅此三层）

每条需求进入 7 阶段 Pipeline：

需求澄清（人主导，AI 追问结构化）
   ↓
UI/UE 设计（AI 出方案，人选择）
   ↓
技术架构（AI 给建议，人做决策）
   ↓
开发实现（Agent 执行，人审查）
   ↓
测试验证（Agent 跑测试，人审阅）
   ↓
部署上线（Agent 准备，人批准）
   ↓
经验沉淀（AI 提取，人确认）

每个阶段有质量门禁 — 不达标不推进
每个阶段的上下文 — 自动传递给下一阶段
每次完成 — 经验自动提炼入库
```

## 适合谁

**主力用户：有项目交付诉求的"AI 增强型"个体和小团队。**

- **接项目的强个体**：自由职业者 / 独立开发者 / 全栈产品经理，同时管理 2-5 个项目，苦于每个新项目都从零开始
- **小团队管理者**：3-10 人团队的 leader，需要轻量项目管理但不想用 Jira，担心团队经验随人员流动而流失

**不适合：** 需要 SAFe/Jira 这种重型管理的大企业 PMO；纯手动编码不接受 AI 参与的传统团队；只需写个简单页面的轻度用户。

## 当前已落地能力

**项目空间**
- 项目 → 版本 → 需求三层管理
- 版本激活 / 发布 / 未完成需求自动结转
- 轻量项目管理（不做排期、不做人员分配）

**智能管线**
- 七阶段 Pipeline 引擎（含质量门禁校验）
- 阶段对话 + 产出物管理
- 跳过 / 回滚支持

**经验引擎**
- 个人经验 + 项目经验双维度
- 向量语义搜索（pgvector）
- 置信度评分 + 复用次数追踪
- 相似经验自动召回

**Agent 编排**
- 多 Agent 接入（OpenHands / Codex / Claude Code / Cursor）
- 多模型适配（Anthropic / OpenAI / DeepSeek）+ 韧性层
- Registry + Adapter 模式，按需分发

**工程基础**
- 用户认证（账号密码 + 短信验证码 + JWT 双令牌）
- 实时对话（WebSocket）
- API 限流（IP 滑动窗口）+ SMS 防刷
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

环境要求：Docker & Docker Compose · Node.js >= 22 · Python 3.12

### 1. 克隆项目

```bash
git clone https://github.com/zqshi/arc.git
cd arc
```

### 2. 环境配置

```bash
cp .env.example .env
# 编辑 .env，至少填写一个 LLM API Key
# 生产环境必须设置 ARC_JWT_SECRET（openssl rand -hex 32）
```

### 3. 启动

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

## 上线前配置

```bash
# 安全（必须）
ARC_JWT_SECRET=<openssl rand -hex 32>   # 未设置拒绝启动
ARC_DEBUG=false
ARC_CORS_ORIGINS=https://your-domain

# 数据库（必须）
ARC_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/arc

# AI（至少配一个）
ARC_ANTHROPIC_API_KEY=sk-ant-...
ARC_OPENAI_API_KEY=sk-...
ARC_DEEPSEEK_API_KEY=sk-...

# 短信（生产不要用 mock）
ARC_SMS_MOCK_MODE=false
```

完整变量说明见 [.env.example](.env.example)（与 `backend/src/arc/config.py` 一一对应）。

## 常用命令

```bash
docker compose up -d                              # 全栈启动
ARC_DEBUG=true uvicorn arc.main:app --reload      # 后端开发
cd frontend && npm run dev                        # 前端开发
cd backend && pytest -x                           # 后端测试
cd frontend && npm test                           # 前端测试
cd backend && ruff check src/                     # lint
cd backend && alembic upgrade head                # 数据库迁移
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
│       │   └── experience/      #   经验引擎（向量搜索 + 双维度积累）
│       ├── infrastructure/      # 基础设施层（ORM、仓库实现、连接池）
│       └── interface/           # 接口层
│           ├── routes/          #   REST API（分页）
│           ├── ws/              #   WebSocket（对话）
│           ├── schemas/         #   请求/响应 Schema
│           └── middleware/      #   中间件（API 限流）
├── frontend/src/
│   ├── api/                     # API 客户端（Token 主动刷新）
│   ├── components/              # UI 组件 + Artifact 渲染器
│   ├── contexts/                # React Context
│   ├── hooks/                   # 自定义 Hooks
│   └── pages/                   # 页面
├── docs/                        # 产品愿景、模块拆解、设计文档
├── docker-compose.yml           # 4 服务编排
├── CONTRIBUTING.md              # 文档对齐规范
├── CHANGELOG.md                 # 变更日志
└── .env.example                 # 环境变量模板
```

## 文档导航

- 产品愿景：[docs/arc-product-vision.md](./docs/arc-product-vision.md)
- 模块拆解：[docs/arc-module-breakdown.md](./docs/arc-module-breakdown.md)
- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 贡献规范：[CONTRIBUTING.md](./CONTRIBUTING.md)
- 环境变量：[.env.example](./.env.example)
- API 文档：启动后访问 http://localhost:8000/docs

## 阶段性目标

| 阶段 | 目标 | 验证标准 |
|------|------|----------|
| Phase 0 | 核心验证 — "上下文零断裂"是否成立 | 用 Arc 开发 Arc 的下一个 feature，比不用明显更高效 |
| Phase 1 | 项目级体验 — 多项目 + 经验双维度 | 同时管理 2+ 项目，项目经验隔离、个人经验跨项目复用 |
| Phase 2 | 多用户 + 团队协作 | 3-5 人团队用 Arc 管理项目，团队经验库有实际使用 |
| Phase 3 | 商业化 — 云端 + 定价 + 集成 | 可售卖的产品 |

## 许可

[MIT](https://opensource.org/licenses/MIT)

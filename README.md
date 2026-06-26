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
- 需求依赖关系系统（阻塞状态展示、依赖图）
- 多租户隔离架构（Organization + Membership + org-scoped 查询）

**双模式交付引擎**
- **Pipeline 模式**：七阶段 Pipeline（含质量门禁校验）、阶段对话 + 产出物管理、跳过 / 回滚
- **Conversation 模式**：自由对话驱动、AgentLoop 目标驱动 + AutoPilot 自驾模式（最大 12 轮）
- 交付物 8 环节拆分（交互设计 / 视觉规范 / 原型设计独立）
- 原型产品预览（Blob URL + S3 持久化发布）

**领域建模**
- 项目级领域模型自动提取（从技术架构交付物沉淀）
- DDD 三阶段自主建模（战略设计 → 事件风暴 → 战术建模，AI 自主驱动无需人工干预）
- 事件风暴数据提取（领域事件 + 命令自动合并到聚合模型）
- LLM 驱动领域模型质量评审（战略 / 战术 / 命名 / 完整度四维度，评分 + 问题列表 + 改进建议）
- 战略设计（子域划分 + 限界上下文）+ 战术设计（聚合 / 实体 / 值对象 / 领域事件）
- 依赖关系图可视化（SVG 连线 + hover 高亮 + 点击锁定 + 空状态 fallback 分组）
- 增量合并刷新（手动触发 + 自动提取，持续累积不丢弃）

**经验引擎**
- 个人经验 + 项目经验双维度
- 向量语义搜索（pgvector）+ 相似经验自动召回
- 置信度半衰期衰减（基于最后使用时间，活跃经验不过期）
- 经验提炼（项目经验 → 个人经验，AI 去项目细节）
- 批量经验提取（手动触发 + 自动提取）
- 复用效果追踪（类别聚合、过期统计、top 复用排名）

**Agent 编排**
- 多 Agent 接入（OpenHands / Codex / Claude Code / Cursor）
- 多模型适配（Anthropic / OpenAI / DeepSeek）+ 韧性层
- Registry + Adapter 模式，按需分发

**商业化基础**
- Free / Pro / Team 三级定价（QuotaService + UsageDaily + 前端用量展示）
- GitHub 集成（Issue ↔ Todo 双向同步、Webhook HMAC-SHA256 验证）
- 云端部署方案（docker-compose.prod.yml、K8s manifests、GHCR CI/CD）

**工程基础**
- 用户认证（账号密码 + 短信验证码 + JWT 双令牌 + refresh token 吊销）
- 角色权限体系（admin / member / viewer，项目成员管理）
- 实时对话（WebSocket + IDOR 防护）
- SSE 自动重连 + 心跳检测
- API 限流（IP 滑动窗口）+ SMS 防刷
- 安全加固（路径遍历防护、CSP 注入、FK 索引优化）
- Docker 一键部署（多阶段构建、非 root 运行）

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | Python 3.12 · FastAPI · SQLAlchemy (async) · DDD 四层架构 |
| 数据 | PostgreSQL 16 (pgvector) · Alembic Migration |
| 前端 | React 19 · TypeScript 6 · Vite 8 · Tailwind CSS 4 · PWA (Workbox) |
| AI | Anthropic · OpenAI · DeepSeek（多模型动态切换 + 韧性层） |
| Agent | OpenHands · Codex · Claude Code · Cursor（Registry + Adapter） |
| 部署 | Docker Compose · K8s manifests · GHCR CI/CD · 非 root 运行 |
| 存储 | S3 + BaaS 统一存储层（StorageAdapter） |

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

## Kubernetes 部署

生产环境可用 `kubectl apply -k k8s/` 一键部署。**应用前必须完成两步前置**，否则部署会失败：

```bash
# 1. 生成真实 Secret（k8s/secrets.example.yml 仅是占位模板，真实 secrets.yml 被 .gitignore 忽略，不入库）
cp k8s/secrets.example.yml k8s/secrets.yml
#   填入真实值：ARC_DATABASE_URL / ARC_JWT_SECRET / 至少一个 LLM Key / ARC_CORS_ORIGINS
#   签名凭证密钥 ARC_SIGNING_SECRET_KEY 生成：
#     python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. 替换镜像仓库占位符（k8s/kustomization.yml 中 ghcr.io/YOUR_ORG/arc-backend|arc-frontend）
#   改为实际的 GHCR 组织或私有镜像仓库地址
```

```bash
kubectl apply -k k8s/
```

部署清单说明：
- `namespace.yml` — 创建 arc 命名空间
- `configmap.yml` — 非敏感配置（对应 `backend/src/arc/config.py` 字段）
- `secrets.yml` — 敏感配置（**不入库，由 `secrets.example.yml` 复制生成**）
- `backend.yml` / `frontend.yml` / `redis.yml` — 工作负载
- `ingress.yml` — 入口路由

> 本地存储模式（未配 `ARC_STORAGE_ENDPOINT`）需为 backend Pod 挂载可写卷并设置 `ARC_PREVIEW_STATIC_DIR=/app/data/static/previews`，否则预览静态文件写入会失败；生产建议配置对象存储。

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
│       │   ├── experience/      #   经验实体（衰减、复用追踪）
│       │   ├── todo/            #   需求实体 + 值对象
│       │   └── artifact/        #   交付物实体
│       ├── application/         # 应用层
│       │   ├── agent/           #   多 Agent 编排（Registry + Adapter）
│       │   ├── ai/              #   LLM 适配器 + 韧性层
│       │   ├── auth/            #   认证（JWT + SMS + 速率限制）
│       │   ├── execution/       #   AgentLoop + DomainModelExtractor + Validator
│       │   ├── pipeline/        #   七阶段 Pipeline 服务
│       │   ├── planning/        #   规划引擎（文档 + 路线图）
│       │   └── experience/      #   经验引擎（向量搜索 + 双维度积累）
│       ├── infrastructure/      # 基础设施层（ORM、仓库实现、存储适配器）
│       └── interface/           # 接口层
│           ├── routes/          #   REST API（分模块拆分、SQL 分页）
│           ├── ws/              #   WebSocket（对话 + IDOR 防护）
│           ├── schemas/         #   请求/响应 Schema
│           └── middleware/      #   中间件（API 限流、配额拦截）
├── frontend/src/
│   ├── api/                     # API 客户端（Token 主动刷新、SSE 重连）
│   ├── components/              # UI 组件 + Artifact 渲染器
│   │   └── project/             #   项目详情子组件（领域模型图、经验库）
│   ├── contexts/                # React Context
│   ├── hooks/                   # 自定义 Hooks
│   └── pages/                   # 页面
├── docs/                        # 产品愿景、模块拆解、版本管理
│   └── versions/                #   版本 snapshot + backlog
├── k8s/                         # Kubernetes 部署清单
├── docker-compose.yml           # 开发环境编排
├── docker-compose.prod.yml      # 生产环境编排
├── CONTRIBUTING.md              # 文档对齐规范
├── CHANGELOG.md                 # 变更日志
└── .env.example                 # 环境变量模板
```

## 文档导航

- 产品愿景：[docs/arc-product-vision.md](./docs/arc-product-vision.md)
- 模块拆解：[docs/arc-module-breakdown.md](./docs/arc-module-breakdown.md)
- Agent 升级计划：[docs/agent-upgrade-plan.md](./docs/agent-upgrade-plan.md)
- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 贡献规范：[CONTRIBUTING.md](./CONTRIBUTING.md)
- 环境变量：[.env.example](./.env.example)
- API 文档：启动后访问 http://localhost:8000/docs

## 版本历程

| 版本 | 里程碑 | 状态 |
|------|--------|------|
| v0.x | MVP — 项目管理 + Pipeline + 经验库 + Agent 编排 | done |
| v1.0 | 多用户协作 — 角色权限 + 项目成员 + 经验访问控制 | done |
| v1.1 | 工程加固 — 测试覆盖 + 分页统一 + Docker 安全化 | done |
| v1.2 | 交付增强 — AgentLoop + 领域建模 + 原型预览 + S3 存储 | done |
| v2.0 | 商业化 — 多租户 + 计费 + GitHub 集成 + 云部署 | done |
| v2.1 | DDD 工程化 — 三阶段自主建模 + 事件风暴 + LLM 质量评审 + schema 对齐 | done |
| v2.2-2.9 | 质量与智能升级 — ContextEngine + DriftDetection + Checkpoints + GitSync | done |
| v3.0-3.8 | 领域模型升级 — 升级基础设施 + 影响分析 + 升级执行 + 前端贯通 | done |
| v5.1-5.2 | 上下文与优先级 — Prompt注入 + AI Changelog + 优先级可视化 | done |
| v5.3 | 原型预览架构升级 — 版本维度 + S3 持久化 + 空状态保护 | done |
| v5.4 | 部署层真实化 — 存储重构 + Deployment 领域建模 + S3 静态部署 | done |
| v5.5-5.6 | BaaS 升级 — Supabase 运行时 + 领域模型模板 | planned |

## 许可

[MIT](https://opensource.org/licenses/MIT)

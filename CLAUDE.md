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
0. **执行版本完成质量检测协议** (见第 6 章), 全部必修项通过后才能归档
1. 将 `vX.Y.Z-current.md` 精简为 snapshot 格式(删除执行细节, 只保留目标/交付/决策/遗留/约束)
2. 重命名为 `vX.Y.Z-snapshot.md`
3. 将 `vNext-next.md` 重命名为 `vNext-current.md` (激活下一版本)
4. 如果不存在 next.md, 从 `backlog.md` 中取出下一个版本规划, 基于 `TEMPLATE.md` 创建
5. 更新 `CHANGELOG.md` 和 `backlog.md`(移除已启动的版本)
6. 为再下一个版本创建 `vX.Y.Z-next.md` (可选, 有规划时提前建)

## 架构与代码规范

### DDD 分层约束

依赖方向: domain ← application ← infrastructure / interface (箭头表示"被依赖")

| 层 | 职责 | 允许依赖 | 禁止依赖 |
|----|------|---------|---------|
| domain | 实体、值对象、仓储接口、领域错误、领域事件 | 仅 Python 标准库 | application, infrastructure, interface |
| application | 用例编排、领域服务组合、DTO 转换 | domain | interface |
| infrastructure | ORM 模型、仓储实现、外部客户端 | domain, application | interface |
| interface | 路由、schema、WebSocket、中间件 | domain, application, infrastructure | — |

**违反即阻断**: 任何 import 违反上表方向的代码不得合入。

### 领域模型保护规则

- 实体行为内聚: 状态变更必须通过实体方法, 禁止外部直接修改属性
- 值对象不可变: 值对象创建后不得修改, 变更通过创建新实例
- 仓储接口在 domain 层定义, infrastructure 层实现, 禁止 domain 依赖具体实现
- 领域错误在 domain 层定义 (domain/errors.py), 不使用 HTTP 状态码或框架异常
- application service 编排领域对象, 不包含领域规则 — 规则属于 entity 或 domain service

### 文件规模与边界

| 规则 | 阈值 | 违反时处理 |
|------|------|----------|
| 单文件行数上限 | **< 500 行** (强制), 500-800 行 (警告, 下版本拆分) | 超 800 行 = 当版本必修项 |
| 单函数/方法行数 | **< 80 行** | 超出即拆分 |
| 单文件职责 | 一个文件对应一个聚合/服务/组件 | 多职责即拆分 |

> 例外: 纯数据/prompt 文件 (seeds/data.py, prompts.py, types/api.ts) 允许超限, 但必须在文件头注释说明原因。

### 耦合控制

- **禁止循环依赖**: 模块间不得出现 A→B→A 的 import 环
- **依赖方向单向**: 上层调用下层通过接口, domain 定义 repository 接口, infrastructure 实现
- **跨模块通信**: 同层模块间通过 application service 编排, 不直接互调 repository
- **route 层零逻辑**: 只做参数校验 + service 调用, 不写业务判断

### 后端 (Python + FastAPI)

- 新 API 路由必须挂载 auth 依赖
- 列表 API 必须支持分页 (skip/limit)
- 数据库变更必须有 alembic migration
- 新表必须添加必要索引

### 前端 (React + TypeScript + Vite)

- 状态管理以服务端为主, 前端轻量
- 新页面必须支持 PWA 离线降级
- 组件拆分: 超过 300 行必须拆子组件
- props 超过 5 个考虑是否职责过重

### 通用

- commit message 格式: `type: 中文描述` (feat/fix/refactor/docs/test/chore)
- 不引入新的外部依赖前先评估是否必要
- API 响应格式保持一致, 错误用 HTTPException

## 测试规范

### TDD 工作流

新功能开发遵循 Red → Green → Refactor:
1. **Red**: 先写失败的测试, 明确预期行为
2. **Green**: 写最少代码让测试通过
3. **Refactor**: 在测试保护下重构

> domain 层实体和 application 层核心 service **必须** test-first。
> 其他层鼓励但不强制, 至少做到代码与测试同 PR。

### 单元测试规范

**范围**: domain 实体/值对象/领域服务, application service 纯逻辑

**目录结构**: `tests/unit/` 下镜像 src 目录结构
```
tests/unit/
  domain/
    test_{module}_entity.py      ← 对应 domain/{module}/entity.py
    test_{module}_value_objects.py
  application/
    test_{service_name}.py       ← 对应 application/{module}/service.py
```

**编写规则**:
- 一个测试类对应一个被测类/行为族, 以 `Test{ClassName}` 命名
- 测试方法命名: `test_{行为}_{条件}_{预期}`, 如 `test_complete_when_pending_raises`
- domain 层测试**零 mock**: 直接构造实体, 验证行为, 不 mock 任何依赖
- application 层测试 mock 外部依赖 (repository/LLM/外部客户端), 不 mock 领域对象
- 每个测试只验证一个行为, 不在一个 test 方法里塞多个断言路径
- 使用 pytest fixture 管理测试数据, 不在测试方法里硬编码复杂构造

**必须覆盖的场景**:
- 实体创建 (默认值、全字段)
- 状态转换 (合法路径 + 非法路径抛异常)
- 值对象等值性和不可变性
- 边界条件 (空值、极值、重复调用)

### 集成测试规范

**范围**: 涉及数据库、HTTP 请求、WebSocket 的完整链路

**目录结构**: `tests/integration/`

**基础设施**:
- `conftest.py` 提供 `db_session` 和 `client` fixture
- `db_session`: 真实数据库连接, 测试后 rollback
- `client`: httpx.AsyncClient + ASGITransport, 覆盖 auth 依赖注入测试用户
- 使用 `asyncio_mode = "auto"`, 所有 async 测试自动运行

**编写规则**:
- 每个 API 模块至少一个集成测试文件: `test_{module}.py`
- 必须覆盖 CRUD 全路径: 创建 → 查询 → 更新 → 删除
- 必须覆盖权限边界: 未认证请求 → 401, 越权访问 → 403/404
- 必须覆盖分页: 创建多条记录, 验证 skip/limit 参数
- 不 mock 数据库: 集成测试的价值在于打通真实链路
- 测试间无状态依赖: 每个测试自己创建所需数据, 不依赖其他测试的副作用

**命名**: `Test{Module}CRUD`, `Test{Module}Permissions`, `Test{Module}Edge`

### 前端测试规范

**框架**: Vitest + Testing Library, environment: jsdom

**编写规则**:
- 组件测试以用户行为驱动: 用 `screen.getByText` / `fireEvent` / `userEvent`, 不测内部 state
- hook 测试使用 `renderHook`, 验证返回值和副作用
- API client 测试 mock fetch, 验证请求参数和响应处理
- ErrorBoundary 等基础组件必须有测试

**覆盖优先级**:
1. 共享组件 (被 3+ 处引用)
2. 核心页面关键交互路径
3. 自定义 hooks

### 新增代码测试规则

| 变更类型 | 测试要求 |
|---------|---------|
| 新增 domain 实体/值对象 | 同 PR 必须包含单元测试 |
| 新增 application service | 同 PR 必须包含单元测试 |
| 新增 API 端点 | 同 PR 必须包含至少 happy path 集成测试 |
| 修复 bug | 同 PR 必须包含复现该 bug 的回归测试 |
| 重构 | 现有测试全部通过, 不降低覆盖率 |

### 测试运行

| 场景 | 命令 | 时机 |
|------|------|------|
| 后端单元测试 | `pytest tests/unit -x --tb=short` | 每次提交前 |
| 后端集成测试 | `pytest tests/integration -x --tb=short` | PR 合并前 |
| 前端测试 | `npm test` (vitest run) | 每次提交前 |
| CI 全量 | 后端 pytest + 前端 vitest + tsc + build | PR 合并时自动 |

## 版本完成质量检测协议

**触发时机**: 版本所有任务标记 done → 执行检测 → 通过后才归档 snapshot。

### 检测项

#### 6.1 死代码与孤立文件 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| 前端组件/hooks/脚本 | 检查是否被 import 或有 npm script 入口 | 删除 |
| 后端模块 | 检查是否在 routes/service/main 调用链上 | 删除 |

#### 6.2 依赖卫生 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| package.json dependencies | 每个包在 src/ 中有 import | 移除 |
| pyproject.toml dependencies | 每个包在 src/ 中有 import | 移除 |

#### 6.3 配置一致性 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| config.py ↔ .env.example | Settings 字段与 env key 双向对齐 | 补齐 |
| docker-compose ↔ Dockerfile | 端口/镜像名/环境变量一致 | 修正 |
| k8s ↔ Dockerfile | 端口/镜像名一致, 无占位符 | 修正或参数化 |

#### 6.4 文档对齐 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| CLAUDE.md 文档索引路径 | 验证路径实际存在 | 更新索引 |
| CONTRIBUTING.md 引用路径 | 验证路径实际存在 | 修正 |
| backlog.md | 已完成版本只保留一行链接 | 清理 |
| docs/versions/ | 有且仅有一个 *-current.md | 修正 |

#### 6.5 架构合规 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| DDD 层级依赖 | 扫描 import, 验证不违反分层方向 | 立即修复 |
| 循环依赖 | 检测模块间 import 环 | 立即修复 |
| 文件行数 | 扫描所有源文件行数 | > 800 行 = 本版本拆分; 500-800 = 记入技术债务 |

#### 6.6 测试覆盖 [记录]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| domain 层各模块 | 检查 tests/ 下有对应测试文件 | 记入下版本技术债务 |
| application 层各模块 | 检查 tests/ 下有对应测试文件 | 记入下版本技术债务 |
| 新增代码 | 检查本版本新增的 entity/service/endpoint 是否有测试 | 记入下版本技术债务 |

#### 6.7 仓库卫生 [必修]

| 检测对象 | 方法 | 不通过 = |
|---------|------|---------|
| .gitignore 完备性 | git status 中 untracked 文件不应有构建产物/缓存 | 补 gitignore |
| 误入文件 | 不该出现的目录 (如前端下 .pytest_cache) | 删除 |
| 敏感文件 | .env / credentials 不被 git track | 从历史移除 |

### 执行规则

- 6.1-6.5、6.7 为 **必修项**, 全部通过才能归档
- 6.6 为 **记录项**, 记入 snapshot 的 `## 遗留` 和 backlog 技术债务表
- 在 snapshot 文件中新增 `## 质量检测` 小节, 记录本次检测结果摘要

## 周期性质量巡检

### 目的

防止领域模型腐烂、架构约束被渐进侵蚀、技术债务无声积累。
不依赖"版本完成"这一个时间点, 而是在日常开发中持续守护。

### 会话级巡检 (每次会话开始)

上下文加载协议完成后, 追加以下轻量检测:

| # | 检测项 | 方法 | 耗时 |
|---|--------|------|------|
| 1 | DDD 层级依赖 | 扫描 domain/ 下所有 import, 验证无 application/infrastructure/interface 依赖 | < 10s |
| 2 | 循环依赖 | 检测模块间是否有 import 环 | < 10s |
| 3 | 文件超限 | 扫描所有源文件行数, 报告 > 500 行的文件 | < 10s |

- 发现违规 → 在开始任务前先修复, 或记入 current.md 任务表
- 未发现问题 → 静默通过, 不输出

### 任务级巡检 (每个任务完成后)

完成一个开发任务、更新 current.md 状态之前:

| # | 检测项 | 方法 |
|---|--------|------|
| 1 | 本次变更文件是否超限 | 检查本次修改/新增的文件行数 |
| 2 | 本次变更是否引入层级违规 | 检查本次修改文件的 import |
| 3 | 本次新增代码是否有配套测试 | 按测试规范中新增代码测试规则检查 |
| 4 | 本次变更是否影响配置一致性 | 如改了 config.py → 检查 .env.example |

- 发现问题 → 当场修复后再标记任务 done
- 不通过不得标记完成

### 领域模型健康度专项 (每 3 个版本或每月一次)

以下检测在版本完成质量检测之外, 额外执行一次深度审计:

| # | 检测项 | 判定标准 | 腐烂信号 |
|---|--------|---------|---------|
| 1 | 实体行为完整性 | entity 是否只有数据字段没有行为方法 | 贫血模型: entity 退化为纯数据容器 |
| 2 | service 膨胀度 | application service 单文件是否超限, 单方法是否超 80 行 | 逻辑从 domain 泄漏到 service |
| 3 | repository 接口 vs 实现对齐 | domain 定义的 repository 方法是否都有 infrastructure 实现 | 接口与实现漂移 |
| 4 | 值对象使用率 | 是否存在应为值对象但用了裸 str/dict 的字段 | 领域概念未显式建模 |
| 5 | 跨聚合直接访问 | service 是否直接操作其他聚合的 repository | 聚合边界被穿透 |
| 6 | route 层逻辑量 | route 文件中是否出现 if/for 业务判断 | 逻辑从 service 泄漏到 route |

- 发现腐烂信号 → 立即创建技术债务任务, 标注优先级
- P1 (贫血模型/层级泄漏) → 下一版本必修
- P2 (接口漂移/值对象缺失) → 两版本内修复
- P3 (route 轻微逻辑) → 顺手修复

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

# Arc 模块拆解与MVP定义

> 基于 arc-product-vision.md 的全景思考，拆解为实施级别的模块定义。
> 每个模块标注：当前状态（已有/需新建/需升级）、功能清单、MVP边界。

---

## 模块总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Arc 产品模块                                 │
├──────────┬───────────┬───────────┬───────────┬──────────┬───────────┤
│ M1       │ M2        │ M3        │ M4        │ M5       │ M6        │
│ 项目空间  │ 需求管理   │ 智能管线   │ AI对话     │ Agent编排 │ 经验引擎   │
│ ★新建    │ ▲升级     │ ●已有     │ ▲升级     │ ●已有    │ ▲升级     │
├──────────┴───────────┴───────────┴───────────┴──────────┴───────────┤
│                    M7 统一上下文层（★新建 · 基础设施）                  │
├────────────────────────────────────────────────────────────────────-─┤
│                    M8 产出物系统（●已有 · 几乎不动）                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## M1 项目空间（Project Space）★新建

### 当前状态

**不存在。** 当前系统的顶层实体是Todo，没有项目和版本的概念。所有待办平铺在一个列表里。

### 功能清单

| # | 功能 | 说明 | MVP |
|---|---|---|---|
| 1.1 | 项目CRUD | 创建、编辑、归档项目 | Yes |
| 1.2 | 项目配置 | 技术栈偏好、代码仓库URL、项目规范（给AI的永久上下文） | Yes |
| 1.3 | 版本/迭代管理 | 创建版本、设定版本目标、关联需求到版本 | Yes |
| 1.4 | 版本状态流转 | 规划中→进行中→已发布 | Yes |
| 1.5 | 项目仪表盘 | 项目级的需求进度、经验统计 | No |
| 1.6 | 项目列表/切换 | 多项目间快速切换 | Yes |

### 领域模型（新增）

```
Project
  id: UUID
  name: str
  description: str
  tech_stack: str          # 技术栈描述，注入AI上下文
  repo_url: str            # 代码仓库地址
  conventions: str         # 项目规范/约定，注入AI上下文
  status: active|archived
  created_at / updated_at

Version
  id: UUID
  project_id: UUID (FK → Project)
  name: str                # e.g. "v1.0", "Sprint 3"
  goal: str                # 版本目标（一句话）
  status: planning|active|released
  created_at / updated_at
```

### 需要新建的代码

| 层 | 文件 | 说明 |
|---|---|---|
| domain | `domain/project/entity.py` | Project、Version实体 |
| domain | `domain/project/value_objects.py` | ProjectStatus、VersionStatus |
| domain | `domain/project/repository.py` | 仓库接口 |
| infra | `infrastructure/models/project.py` | ORM模型 |
| infra | `infrastructure/repositories/project.py` | 仓库实现 |
| interface | `interface/routes/project.py` | REST路由 |
| interface | `interface/schemas/project.py` | Pydantic schemas |
| migration | `alembic/versions/xxx_add_project.py` | 数据库迁移 |
| frontend | `pages/ProjectList.tsx` | 项目列表页 |
| frontend | `pages/ProjectDetail.tsx` | 项目详情/设置页 |
| frontend | `components/VersionManager.tsx` | 版本管理组件 |
| frontend | `types/api.ts` | 新增Project、Version类型 |

---

## M2 需求管理（Requirement Management）▲升级

### 当前状态

**已有Todo实体和完整CRUD。** 但缺少项目/版本关联和需求依赖。

当前Todo模型：
```python
# domain/todo/entity.py
Todo(title, description, id, status, current_phase, tags, error_reason)

# infrastructure/models/todo.py — 表结构
todos(id, title, description, status, current_phase, tags, created_at, updated_at)
```

### 需要升级的内容

| # | 功能 | 当前状态 | 变更 | MVP |
|---|---|---|---|---|
| 2.1 | 项目归属 | 无 | Todo新增`project_id`外键 | Yes |
| 2.2 | 版本归属 | 无 | Todo新增`version_id`外键 | Yes |
| 2.3 | 需求依赖 | 无 | 新增`todo_dependencies`关联表（blocked_by关系） | No |
| 2.4 | 需求优先级 | 无 | Todo新增`priority`字段（P0-P3） | Yes |
| 2.5 | 按项目筛选 | 无 | 列表页支持按项目和版本过滤 | Yes |
| 2.6 | 需求CRUD | 已有 | 创建时关联project_id和version_id | Yes |
| 2.7 | 状态机 | 已有 | 不变 | — |

### 代码变更

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `domain/todo/entity.py` | 修改 | 新增project_id、version_id、priority字段 |
| `infrastructure/models/todo.py` | 修改 | 新增外键列 |
| `interface/schemas/todo.py` | 修改 | 请求/响应schema加字段 |
| `interface/routes/todo.py` | 修改 | 列表接口加project_id、version_id过滤参数 |
| `infrastructure/repositories/todo.py` | 修改 | 查询加过滤条件 |
| `alembic/versions/xxx_add_project_fk.py` | 新增 | 迁移：加列+外键 |
| `frontend/types/api.ts` | 修改 | Todo类型加字段 |
| `frontend/pages/TodoList.tsx` | 修改 | 按项目/版本过滤 |
| `frontend/components/CreateTodoModal.tsx` | 修改 | 创建时选择项目和版本 |

---

## M3 智能管线（Pipeline）●已有

### 当前状态

**已完整实现。** 7阶段流水线、状态机、质量门禁、跳过/回滚、Agent执行集成全部到位。

当前能力：
- `PipelineService.initialize_pipeline()` — 创建7个阶段实例
- `PipelineService.start_phase()` — 激活阶段并创建对话
- `PipelineService.generate_artifact()` — AI生成产出物
- `PipelineService.confirm_phase()` — Gate检查 + 确认 + 推进下一阶段
- `PipelineService.skip_phase()` — 跳过（部分阶段不可跳过）
- `PipelineService.rollback_to()` — 回滚到指定阶段
- `PipelineService.execute_with_agent()` — Agent执行（dev/test/deploy）

### 需要升级的内容

| # | 功能 | 当前状态 | 变更 | MVP |
|---|---|---|---|---|
| 3.1 | 阶段编排 | 已有，完整 | 不变 | — |
| 3.2 | 质量门禁 | 已有 | Gate评估时注入项目规范作为评判标准 | Yes |
| 3.3 | 上下文组装 | 已有，Todo级 | 升级为注入项目级上下文（M7驱动） | Yes |
| 3.4 | 阶段产出物链 | 已有 | 不变 | — |

### 代码变更

变更量极小，主要由M7（统一上下文层）驱动。pipeline/service.py本身几乎不动。

---

## M4 AI对话（Conversation）▲升级

### 当前状态

**已有完整实现。** 多轮对话、WebSocket流式响应、阶段感知的system prompt、经验注入。

当前`ConversationService._build_system_prompt()`已经做了：
- 阶段特定的system prompt模板
- 上游已确认产出物注入
- 相关经验检索和注入（全局/项目/待办三级scope）
- 苏格拉底式追问（需求澄清阶段）

### 需要升级的内容

| # | 功能 | 当前状态 | 变更 | MVP |
|---|---|---|---|---|
| 4.1 | 阶段prompt | 已有 | 不变 | — |
| 4.2 | 上游产出物注入 | 已有 | 不变 | — |
| 4.3 | 经验注入 | 已有（三级scope） | 经验筛选时加project_id过滤 | Yes |
| 4.4 | **项目上下文注入** | **不存在** | system prompt中注入项目的tech_stack、conventions | Yes |
| 4.5 | **版本目标注入** | **不存在** | system prompt中注入当前版本的goal和scope | Yes |
| 4.6 | **同版本其他需求感知** | **不存在** | 注入同版本其他需求的标题和状态，避免冲突 | No |

### 代码变更

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `application/conversation/service.py` | 修改 | `_build_system_prompt`中调用M7获取项目级上下文 |
| `application/pipeline/prompts.py` | 修改 | prompt模板中增加项目上下文占位符 |

---

## M5 Agent编排（Agent Orchestration）●已有

### 当前状态

**已完整实现。** 多Agent注册表（OpenHands/Claude Code/Codex/Cursor）、会话管理、上下文组装、适配器抽象。

当前`TaskContextBuilder`已经做了：
- 从Todo获取标题、描述
- 从已确认Artifact获取需求规格、UI设计、技术架构、开发报告、测试报告
- 检索相关经验并注入
- 输出为markdown格式发给Agent

### 需要升级的内容

| # | 功能 | 当前状态 | 变更 | MVP |
|---|---|---|---|---|
| 5.1 | 多Agent注册 | 已有 | 不变 | — |
| 5.2 | 会话管理 | 已有 | 不变 | — |
| 5.3 | 上下文组装 | 已有，Todo级 | `TaskContext`增加project-level字段（M7驱动） | Yes |
| 5.4 | 结果回写 | 已有 | 不变 | — |

### 代码变更

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `application/agent/context_builder.py` | 修改 | `TaskContext`增加project_name、tech_stack、conventions字段；`build()`时从项目获取 |

---

## M6 经验引擎（Experience Engine）▲升级

### 当前状态

**已有基础实现。** 经验提取、向量检索、confidence/reuse_count追踪、三级scope（todo/project/global）。

当前Experience模型：
```python
Experience(title, problem, solution, todo_id, scope, decisions, pitfalls,
           applicable_scenarios, tags, embedding, confidence, reuse_count, metadata)
```

**问题：** 当前scope虽然有`project`级别，但没有`project_id`字段——不知道属于哪个项目。当只有一个项目时这不是问题，多项目时就会混乱。

### 需要升级的内容

| # | 功能 | 当前状态 | 变更 | MVP |
|---|---|---|---|---|
| 6.1 | 经验提取 | 已有 | 提取时自动设置scope和project_id | Yes |
| 6.2 | **项目归属** | **不存在** | Experience新增`project_id`外键 | Yes |
| 6.3 | **Scope重定义** | 已有但语义模糊 | `personal`=个人经验（跨项目）；`project`=项目经验（跟项目走） | Yes |
| 6.4 | 语义检索 | 已有 | 检索时按scope和project_id过滤 | Yes |
| 6.5 | 主动注入 | 已有（对话时注入） | 不变，由M4调用时传project_id | — |
| 6.6 | **经验提炼** | **不存在** | 从项目经验中提炼出个人经验（用户确认后） | No |
| 6.7 | **衰减机制** | **不存在** | 经验confidence随时间衰减 | No |
| 6.8 | 经验编辑 | 前端有展示，编辑能力弱 | 经验详情页可编辑所有字段 | No |

### Scope重定义

当前三级scope（todo/project/global）语义不够清晰。建议重定义为：

```
personal — 个人经验，跨项目有效，project_id为空
                例："React项目用TanStack Query比手写useEffect靠谱"

project  — 项目经验，跟项目走，project_id指向具体项目
                例："本项目选PG因为需要pgvector"

去掉global和todo级别：
- global → 合并到personal（个人经验本身就是全局的）
- todo → 合并到project（单个待办的经验归属到项目）
```

### 代码变更

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `domain/experience/entity.py` | 修改 | 新增project_id字段 |
| `domain/todo/value_objects.py` | 修改 | ExperienceScope改为 personal/project |
| `infrastructure/models/experience.py` | 修改 | 新增project_id外键列 |
| `infrastructure/repositories/experience.py` | 修改 | 查询方法加project_id过滤 |
| `application/experience/service.py` | 修改 | 提取时自动设置project_id |
| `application/conversation/service.py` | 修改 | 经验注入时按project_id过滤项目经验 |
| `interface/schemas/experience.py` | 修改 | 响应加project_id |
| `frontend/pages/ExperienceList.tsx` | 修改 | 按项目和scope过滤 |
| `alembic/versions/xxx_experience_project.py` | 新增 | 迁移 |

---

## M7 统一上下文层（Unified Context Layer）★新建

### 当前状态

**不存在为独立模块。** 当前上下文组装分散在两个地方：
- `ConversationService._build_system_prompt()` — 对话时组装上下文
- `TaskContextBuilder.build()` — Agent执行时组装上下文

两者各自独立地获取Todo信息、产出物、经验。如果要在两处都加项目级上下文，会产生重复逻辑。

### 设计

抽取一个`ProjectContextProvider`，作为项目级上下文的统一提供者：

```python
class ProjectContextProvider:
    """提供项目级上下文信息，供对话和Agent上下文组装共用。"""

    async def get_project_context(self, todo_id: UUID) -> ProjectContext:
        """从Todo出发，获取其所属项目和版本的上下文。"""
        # Todo → project_id → Project(name, tech_stack, conventions)
        # Todo → version_id → Version(name, goal)
        # 同版本其他需求列表
        ...

@dataclass
class ProjectContext:
    project_name: str
    project_description: str
    tech_stack: str              # 注入AI prompt
    conventions: str             # 注入AI prompt
    repo_url: str
    version_name: str
    version_goal: str
    sibling_requirements: list[dict]  # 同版本其他需求（标题+状态）
```

### 功能清单

| # | 功能 | 说明 | MVP |
|---|---|---|---|
| 7.1 | ProjectContextProvider | 统一的项目上下文获取 | Yes |
| 7.2 | 对话上下文注入 | ConversationService调用Provider | Yes |
| 7.3 | Agent上下文注入 | TaskContextBuilder调用Provider | Yes |
| 7.4 | 同版本需求感知 | 注入同版本其他需求，避免方案冲突 | No |

### 需要新建的代码

| 文件 | 说明 |
|---|---|
| `application/context/provider.py` | ProjectContextProvider + ProjectContext |
| `application/conversation/service.py` | 修改：调用provider |
| `application/agent/context_builder.py` | 修改：调用provider、TaskContext增字段 |

---

## M8 产出物系统（Artifact）●已有

### 当前状态

**已完整实现，几乎不需要变更。**

已有：7种产出物类型、版本管理、确认/取消确认、按阶段和Todo查询、10个前端渲染器。

### 需要升级的内容

| # | 功能 | 变更 | MVP |
|---|---|---|---|
| 8.1 | 所有现有功能 | 不变 | — |
| 8.2 | 产出物和项目的关联 | 通过Todo.project_id间接关联，无需直接外键 | — |

**结论：M8不需要改动。**

---

## MVP定义

### MVP目标

**验证"上下文零断裂"在项目粒度下是否成立。**

具体标准：用户能在Arc中创建一个项目，在项目下创建版本和需求，需求走完pipeline时AI始终知道项目背景、版本目标、技术栈约定。

### MVP范围

```
M1 项目空间     → 1.1 项目CRUD + 1.2 项目配置 + 1.3 版本管理 + 1.4 版本状态 + 1.6 项目切换
M2 需求管理     → 2.1 项目归属 + 2.2 版本归属 + 2.4 优先级 + 2.5 按项目筛选 + 2.6 创建关联
M3 智能管线     → 3.2 Gate注入项目规范 + 3.3 项目级上下文
M4 AI对话      → 4.3 经验按项目过滤 + 4.4 项目上下文注入 + 4.5 版本目标注入
M5 Agent编排    → 5.3 TaskContext增加项目字段
M6 经验引擎     → 6.1 提取设project_id + 6.2 project_id字段 + 6.3 scope重定义 + 6.4 按项目检索
M7 统一上下文   → 7.1 Provider + 7.2 对话注入 + 7.3 Agent注入
M8 产出物      → 不动
```

### MVP排除项

```
- 需求依赖关系（M2.3）
- 项目仪表盘（M1.5）
- 同版本需求感知（M4.6、M7.4）
- 经验提炼（从项目经验→个人经验）（M6.6）
- 经验衰减机制（M6.7）
- 经验编辑能力增强（M6.8）
```

---

## 与当前代码的差距汇总

### 后端新建文件（约10个）

| 文件 | 模块 | 说明 |
|---|---|---|
| `domain/project/entity.py` | M1 | Project、Version实体 |
| `domain/project/value_objects.py` | M1 | ProjectStatus、VersionStatus |
| `domain/project/repository.py` | M1 | 仓库接口 |
| `infrastructure/models/project.py` | M1 | ORM模型 |
| `infrastructure/repositories/project.py` | M1 | 仓库实现 |
| `interface/routes/project.py` | M1 | REST路由 |
| `interface/schemas/project.py` | M1 | Pydantic schemas |
| `application/context/provider.py` | M7 | 统一上下文Provider |
| `alembic/versions/xxx_add_project.py` | M1 | 项目表迁移 |
| `alembic/versions/xxx_todo_project_fk.py` | M2 | Todo加外键迁移 |
| `alembic/versions/xxx_experience_project.py` | M6 | Experience加project_id迁移 |

### 后端修改文件（约12个）

| 文件 | 模块 | 变更说明 |
|---|---|---|
| `domain/todo/entity.py` | M2 | 新增project_id、version_id、priority |
| `domain/todo/value_objects.py` | M2+M6 | ExperienceScope改为personal/project |
| `domain/experience/entity.py` | M6 | 新增project_id |
| `infrastructure/models/todo.py` | M2 | 新增外键列 |
| `infrastructure/models/experience.py` | M6 | 新增project_id列 |
| `infrastructure/repositories/todo.py` | M2 | 查询加project过滤 |
| `infrastructure/repositories/experience.py` | M6 | 查询加project过滤 |
| `interface/routes/todo.py` | M2 | 列表接口加过滤参数 |
| `interface/schemas/todo.py` | M2 | schema加字段 |
| `application/conversation/service.py` | M4 | 调用ProjectContextProvider |
| `application/agent/context_builder.py` | M5 | TaskContext扩展 + 调用Provider |
| `application/experience/service.py` | M6 | 提取时设置project_id |
| `main.py` | M1 | 注册项目路由 |
| `config.py` | — | 无需变更 |

### 前端新建文件（约4个）

| 文件 | 说明 |
|---|---|
| `pages/ProjectList.tsx` | 项目列表页 |
| `pages/ProjectDetail.tsx` | 项目详情/设置页 |
| `components/VersionManager.tsx` | 版本管理组件 |
| `components/ProjectSelector.tsx` | 项目/版本选择器 |

### 前端修改文件（约7个）

| 文件 | 变更说明 |
|---|---|
| `types/api.ts` | 新增Project、Version类型 |
| `api/client.ts` | 新增项目和版本API方法 |
| `App.tsx` | 新增项目相关路由 |
| `components/Layout.tsx` / `Sidebar.tsx` | 侧边栏增加项目导航 |
| `pages/TodoList.tsx` | 按项目/版本过滤，列表展示调整 |
| `components/CreateTodoModal.tsx` | 创建时选择项目和版本 |
| `pages/ExperienceList.tsx` | 按项目过滤 |

---

## 实施顺序建议

按依赖关系排序：

```
Phase 1 — 地基（无前端依赖，后端可独立跑通）
  ① M1后端：Project/Version领域模型 + ORM + 迁移 + API路由
  ② M2后端：Todo加project_id/version_id + 迁移 + API修改
  ③ M6后端：Experience加project_id + scope重定义 + 迁移

Phase 2 — 管道（上下文流通）
  ④ M7：ProjectContextProvider实现
  ⑤ M4：ConversationService集成Provider
  ⑥ M5：TaskContextBuilder集成Provider
  ⑦ M3：Gate评估注入项目规范

Phase 3 — 界面（前端串联）
  ⑧ 前端：Project/Version页面和组件
  ⑨ 前端：TodoList/CreateModal项目关联
  ⑩ 前端：ExperienceList项目过滤
  ⑪ 前端：Layout/Sidebar项目导航

Phase 4 — 验证
  ⑫ 用Arc创建一个真实项目，走完至少一个需求的完整pipeline
  ⑬ 验证AI对话中是否体现了项目上下文
  ⑭ 验证经验是否正确归属到项目
```

### 工作量估算

| Phase | 后端 | 前端 | 合计 |
|---|---|---|---|
| Phase 1 地基 | ~800行新增 + ~200行修改 | — | ~1000行 |
| Phase 2 管道 | ~300行新增 + ~150行修改 | — | ~450行 |
| Phase 3 界面 | — | ~1500行新增 + ~400行修改 | ~1900行 |
| **合计** | **~1450行** | **~1900行** | **~3350行** |

这个规模意味着：用AI辅助开发的话，Phase 1-3大约2-3天可以完成。

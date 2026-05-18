export interface SeedExperience {
  title: string;
  scope: 'personal' | 'project';
  status: 'draft' | 'confirmed' | 'archived';
  problem: string;
  solution: string;
  decisions: string[];
  pitfalls: string[];
  applicable_scenarios: string;
  tags: { label: string; color: string }[];
  confidence: number;
  reuse_count: number;
  // Which project to link (by index in PROJECTS array), null = personal unlinked
  projectIdx: number | null;
  // Which todo spawned it (projectIdx + versionIdx + todoIdx), null = manually created
  todoRef?: { versionIdx: number; todoIdx: number };
}

export const EXPERIENCES: SeedExperience[] = [
  // ── Arc 工作台 v1.0 完成后沉淀 ──
  {
    title: 'DDD分层架构在FastAPI中的实践',
    scope: 'project',
    status: 'confirmed',
    problem: '传统MVC架构在业务复杂度增长后，Service层变成"上帝类"，路由处理函数超过500行，难以测试和维护。',
    solution: '严格按 domain / application / infrastructure / interface 四层划分。domain层只包含实体和值对象，不依赖任何框架；application层编排用例，通过接口依赖注入infrastructure实现；interface层只做请求解析和响应序列化。',
    decisions: [
      '选择Repository模式而非Active Record：实体不依赖ORM，单元测试可用内存实现替代',
      '用例级事务边界：每个Application Service方法对应一个完整事务',
      'Value Object使用frozen dataclass：不可变性保证线程安全',
    ],
    pitfalls: [
      'FastAPI的Depends注入与DDD的构造函数注入冲突 — 通过工厂函数适配解决',
      '跨聚合引用时循环导入 — 使用TYPE_CHECKING延迟导入 + 接口隔离',
      'SQLAlchemy 2.0异步Session在嵌套事务中的行为不一致 — 统一使用begin_nested()',
    ],
    applicable_scenarios: '适用于业务逻辑复杂、需要长期维护的后端项目。简单CRUD项目不建议引入，overhead大于收益。',
    tags: [{ label: '架构', color: '#A78BFA' }, { label: '后端', color: '#4A9FD8' }, { label: 'DDD', color: '#34D399' }],
    confidence: 0.85,
    reuse_count: 3,
    projectIdx: 0,
    todoRef: { versionIdx: 0, todoIdx: 0 },
  },
  {
    title: 'Pipeline状态机设计 — 有限状态机+事件驱动',
    scope: 'project',
    status: 'confirmed',
    problem: '7阶段Pipeline的状态流转逻辑散落在各处，出现"幽灵状态"（已完成的阶段被重新触发）和"死锁"（阶段间循环等待）。',
    solution: '将Pipeline建模为有限状态机(FSM)：每个Phase有明确的status枚举(pending/active/awaiting_confirm/confirmed/skipped)，状态转换通过显式Transition方法，非法转换抛异常。Gate机制在阶段推进前校验产出物完整性。',
    decisions: [
      '状态转换用白名单而非黑名单：只定义合法的from→to组合',
      'Gate校验独立于Phase逻辑：可插拔的验证规则，便于新增/修改校验条件',
      '回退操作重置后续所有Phase至pending：保证数据一致性，避免脏数据残留',
    ],
    pitfalls: [
      '最初用字符串比较状态导致拼写错误难排查 — 改用StrEnum强类型约束',
      '并发请求导致重复推进 — 在数据库层加乐观锁(version字段)',
      'skipped状态的Phase在回退时不应重置 — 需要区分"主动跳过"和"自动跳过"',
    ],
    applicable_scenarios: '任何包含多步骤、有序执行、需要人工确认卡点的工作流场景：审批流、CI/CD Pipeline、多阶段表单。',
    tags: [{ label: '状态机', color: '#EF4444' }, { label: '设计模式', color: '#F472B6' }, { label: '后端', color: '#4A9FD8' }],
    confidence: 0.92,
    reuse_count: 5,
    projectIdx: 0,
    todoRef: { versionIdx: 0, todoIdx: 1 },
  },
  {
    title: 'LLM多轮对话的上下文窗口管理策略',
    scope: 'personal',
    status: 'confirmed',
    problem: '长对话场景下token数超出模型上下文窗口(128K)，直接截断导致关键信息丢失，用户体验骤降（AI"失忆"）。',
    solution: '三层上下文策略：1) System Prompt固定不变；2) 滑动窗口保留最近N轮对话；3) 超出窗口的历史通过摘要压缩注入。摘要由独立的summarization调用生成，缓存在conversation metadata中。',
    decisions: [
      '摘要粒度选择"每5轮生成一次"而非"每轮增量"：降低API调用成本',
      '窗口大小动态计算(总token budget - system - summary = 剩余给recent)：适配不同模型',
      '关键决策点标记为"不可压缩"：确保重要上下文不被摘要丢失',
    ],
    pitfalls: [
      'tiktoken在中文分词时token数估算偏差大 — 改用模型原生tokenizer做精确计算',
      '摘要本身也会随对话增长无限膨胀 — 增加摘要的摘要(递归压缩)，设上限',
      '并发对话修改同一conversation的摘要导致覆盖 — 加版本号做CAS更新',
    ],
    applicable_scenarios: '所有需要长对话记忆的LLM应用：客服系统、编程助手、文档问答。短对话(<10轮)无需此机制。',
    tags: [{ label: 'AI', color: '#A78BFA' }, { label: 'LLM', color: '#34D399' }, { label: '性能', color: '#EF4444' }],
    confidence: 0.88,
    reuse_count: 4,
    projectIdx: 0,
    todoRef: { versionIdx: 0, todoIdx: 2 },
  },

  // ── 智能客服系统 进行中沉淀 ──
  {
    title: 'RAG文档分块的最佳实践 — 语义完整性优先',
    scope: 'project',
    status: 'confirmed',
    problem: '固定512 token分块导致表格被切断、代码块不完整、段落语义割裂，检索召回率低于60%。',
    solution: '混合分块策略：1) Markdown按标题层级递归拆分；2) 表格/代码块作为整体不切割（超长时按行拆分）；3) 段落内按句子边界切分，保证每chunk有完整语义单元。overlap设为chunk的15%而非固定token数。',
    decisions: [
      '分块粒度按文档类型自适应：技术文档用400token，FAQ用200token，法律文本用600token',
      'overlap使用语义边界(句号/换行)对齐而非硬截断：避免半句话出现在两个chunk中',
      '每个chunk携带父标题链作为metadata：检索时可做层级过滤和上下文扩展',
    ],
    pitfalls: [
      'PDF解析后格式信息丢失导致分块策略失效 — 先用结构化解析(pdf2md)再分块',
      '中文句子边界检测比英文复杂(无空格分隔) — 使用jieba的句子切分而非正则',
      '表格整体作为chunk后embedding质量差 — 将表格转为描述性文本再embedding',
    ],
    applicable_scenarios: '所有RAG系统的文档预处理阶段。纯结构化数据(JSON/CSV)不适用，应直接建索引。',
    tags: [{ label: 'RAG', color: '#A78BFA' }, { label: 'AI', color: '#34D399' }, { label: '搜索', color: '#4A9FD8' }],
    confidence: 0.78,
    reuse_count: 2,
    projectIdx: 1,
    todoRef: { versionIdx: 0, todoIdx: 0 },
  },
  {
    title: 'LangChain对话链中的意图识别与路由',
    scope: 'project',
    status: 'draft',
    problem: '单一对话链无法区分用户意图（查询/闲聊/投诉/操作请求），所有输入都走RAG检索导致无关回复和资源浪费。',
    solution: '在对话链前增加Intent Router：用轻量分类模型(或few-shot LLM)识别意图类别，路由到专门的子链处理。每个子链有独立的prompt模板和工具集。',
    decisions: [
      '意图分类用few-shot而非fine-tune：灵活性高、可随时增加新意图类别',
      '兜底策略选择"回退到通用RAG"而非"拒绝回答"：用户体验优先',
      '路由结果缓存同一session内的意图判断：避免相似问题重复分类',
    ],
    pitfalls: [
      '意图边界模糊时分类器置信度低 — 设0.7阈值，低于则走多链并行取最佳',
      'LangChain的AgentExecutor在多子链切换时上下文污染 — 每个子链维护独立memory',
    ],
    applicable_scenarios: '多功能对话系统（客服/助手类产品）。单一功能的bot(如纯FAQ)不需要路由层。',
    tags: [{ label: 'AI', color: '#A78BFA' }, { label: 'LangChain', color: '#34D399' }, { label: '架构', color: '#F472B6' }],
    confidence: 0.45,
    reuse_count: 0,
    projectIdx: 1,
    todoRef: { versionIdx: 0, todoIdx: 1 },
  },

  // ── 组件设计系统 v0.1 完成后沉淀 ──
  {
    title: 'CSS Custom Properties实现Design Token主题切换',
    scope: 'project',
    status: 'confirmed',
    problem: '硬编码颜色值散落在200+组件文件中，暗色主题需要逐个文件修改，维护成本极高且容易遗漏。',
    solution: '建立三层Token体系：1) Primitive Token(原始色板)；2) Semantic Token(语义映射，如bg-primary/text-secondary)；3) Component Token(组件级覆盖)。通过CSS Custom Properties在:root和[data-theme="dark"]中切换，组件只引用Semantic Token。',
    decisions: [
      'Token命名采用用途而非外观：bg-danger而非bg-red，适应多主题语境',
      '运行时切换而非编译时生成：用户可实时预览主题，无需刷新页面',
      '颜色使用oklch色彩空间：感知均匀性好，生成色阶更自然',
    ],
    pitfalls: [
      'Tailwind CSS的JIT模式不支持动态CSS变量类名 — 使用@theme指令预注册所有token',
      '暗色主题不是简单反转亮度 — 需要独立的色板设计，对比度需单独校验(WCAG AA)',
      'Shadow在暗色背景下几乎不可见 — 暗色主题改用border或微妙的亮边替代阴影',
    ],
    applicable_scenarios: '需要支持多主题（亮/暗/品牌定制）的组件库或应用。单主题项目用Tailwind默认配置即可。',
    tags: [{ label: '设计系统', color: '#F472B6' }, { label: '前端', color: '#E5A93D' }, { label: 'CSS', color: '#4A9FD8' }],
    confidence: 0.90,
    reuse_count: 6,
    projectIdx: 4,
    todoRef: { versionIdx: 0, todoIdx: 0 },
  },
  {
    title: '表单组件统一验证状态与无障碍访问',
    scope: 'project',
    status: 'confirmed',
    problem: '各表单组件(Input/Select/Checkbox)的错误状态样式不一致，验证逻辑重复实现，且缺乏ARIA属性导致屏幕阅读器无法正确读取错误信息。',
    solution: '抽象FormField wrapper组件：统一管理label/error/hint的渲染和ARIA关联。验证逻辑通过composable rules(required/minLength/pattern等)组合，错误状态通过context下发给内部输入组件。',
    decisions: [
      '验证时机选择onBlur而非onChange：减少视觉干扰，用户填完再校验',
      'ARIA方案用aria-describedby关联错误消息而非aria-invalid单独使用：兼容性最广',
      '错误动画使用layoutId而非height transition：避免layout thrashing',
    ],
    pitfalls: [
      'aria-describedby的ID在同页多表单时冲突 — 使用useId()生成唯一前缀',
      'Select组件的Listbox在iOS VoiceOver下焦点管理异常 — 需要额外的role=listbox+aria-activedescendant',
      '实时验证在IME输入法composing期间误触发 — 监听compositionend事件后再校验',
    ],
    applicable_scenarios: '所有需要表单交互的前端项目。特别是ToB/管理后台场景，表单密集，统一体验收益大。',
    tags: [{ label: '组件', color: '#34D399' }, { label: '无障碍', color: '#EF4444' }, { label: '前端', color: '#E5A93D' }],
    confidence: 0.82,
    reuse_count: 4,
    projectIdx: 4,
    todoRef: { versionIdx: 0, todoIdx: 1 },
  },

  // ── 个人经验（跨项目通用） ──
  {
    title: 'React 18并发模式下useEffect的请求去重',
    scope: 'personal',
    status: 'confirmed',
    problem: 'React 18 StrictMode在开发环境下mount→unmount→remount组件，导致useEffect中的API请求重复发送，数据闪烁，甚至创建类操作被执行两次。',
    solution: '使用AbortController在cleanup中取消进行中的请求，配合useRef标记是否已完成避免状态更新。生产环境StrictMode不重复mount，但该模式能暴露潜在的竞态条件。',
    decisions: [
      '不使用useEffect ignore flag模式(有内存泄漏风险) — 统一用AbortController',
      '数据获取层迁移到useSWR/React Query而非手写effect：内置去重、缓存、重试',
      '创建/修改操作使用event handler而非effect触发：避免strict mode重复执行',
    ],
    pitfalls: [
      'AbortController.abort()后fetch抛AbortError需要在catch中过滤 — 否则错误边界误触发',
      'useSWR的dedupingInterval默认2秒在快速切换tab时仍可能重复 — 设为0+手动mutate控制',
      'React Query在SSR场景下hydration时会重新fetch — 需要配置staleTime > 0',
    ],
    applicable_scenarios: 'React 18+的所有项目。React 17及以下不受StrictMode double-mount影响，但AbortController最佳实践仍推荐。',
    tags: [{ label: 'React', color: '#61DAFB' }, { label: '前端', color: '#E5A93D' }, { label: '性能', color: '#EF4444' }],
    confidence: 0.95,
    reuse_count: 8,
    projectIdx: null,
  },
  {
    title: 'PostgreSQL JSONB字段查询性能优化',
    scope: 'personal',
    status: 'confirmed',
    problem: 'JSONB字段使用->>/->操作符做WHERE过滤时，全表扫描导致查询时间从5ms退化到800ms+（10万行数据规模）。',
    solution: '针对高频查询路径创建GIN索引(jsonb_path_ops)；对固定结构的嵌套字段创建表达式索引；超大JSON考虑提取到独立列做B-tree索引。避免在WHERE中使用@>配合大JSON文档匹配。',
    decisions: [
      'GIN索引选jsonb_path_ops而非默认操作符类：空间节省60%，@>和?操作符够用',
      '频繁过滤的顶层字段抽取为generated column：获得B-tree索引的精确匹配性能',
      '聚合查询使用物化视图+定时刷新而非实时计算：trade-off新鲜度换吞吐量',
    ],
    pitfalls: [
      'GIN索引不支持比较操作符(>, <) — 范围查询仍需expression index',
      'jsonb_path_ops不支持?/?&/?|操作符 — 需要key存在性检查时用默认GIN',
      'JSONB数组元素上的索引需要专门的jsonb_to_recordset展开 — 大数组性能仍差',
    ],
    applicable_scenarios: 'PostgreSQL中使用JSONB存储半结构化数据且查询量>100QPS的场景。数据量<1万行时索引收益可忽略。',
    tags: [{ label: '数据库', color: '#336791' }, { label: '性能', color: '#EF4444' }, { label: 'PostgreSQL', color: '#4A9FD8' }],
    confidence: 0.91,
    reuse_count: 6,
    projectIdx: null,
  },
  {
    title: 'Tailwind CSS v4迁移踩坑全记录',
    scope: 'personal',
    status: 'draft',
    problem: '从Tailwind CSS v3迁移到v4时，@apply指令行为变化、配置文件格式变更(tailwind.config.js→CSS @theme)、JIT引擎重写导致大量样式失效。',
    solution: '分三步迁移：1) 运行官方codemod处理基础语法；2) 手动迁移@theme配置和插件；3) 逐页面视觉回归测试。保留v3配置作为fallback，灰度切换。',
    decisions: [
      '迁移节奏选择"逐模块"而非"big bang"：降低风险，每个PR可独立回滚',
      '自定义插件改用@plugin API而非addUtilities：v4原生支持，性能更好',
      '放弃tailwind.config.js改用CSS-first配置：与IDE的CSS智能提示更好集成',
    ],
    pitfalls: [
      '@apply在v4中不支持任意值类 — 需改为直接写内联style或提取为@utility',
      'dark:变体从media改为class策略时v4默认行为变了 — 需显式配置darkMode',
      'content路径配置从JS移到CSS @source后，monorepo的包引用路径要调整',
    ],
    applicable_scenarios: '所有使用Tailwind CSS v3需要升级到v4的项目。新项目直接用v4无此问题。',
    tags: [{ label: 'CSS', color: '#38BDF8' }, { label: '前端', color: '#E5A93D' }, { label: '迁移', color: '#F59E0B' }],
    confidence: 0.55,
    reuse_count: 1,
    projectIdx: null,
  },

  // ── Legacy API Gateway 归档项目的历史经验 ──
  {
    title: 'JWT多租户Token隔离与密钥轮换',
    scope: 'project',
    status: 'archived',
    problem: '所有租户共用同一JWT密钥，一旦泄露影响全部用户；密钥轮换需要停机重新签发所有token。',
    solution: '每个租户独立密钥对，JWT header中携带kid(key ID)指向当前有效密钥。密钥轮换时新旧密钥并存(grace period)，新签发用新密钥，验证时按kid查找对应密钥。',
    decisions: [
      '密钥存储选择Vault而非环境变量：支持自动轮换和审计日志',
      'Token有效期设置15分钟+Refresh Token机制：缩小泄露影响窗口',
      'kid格式用timestamp前缀：可快速判断密钥新旧，便于清理过期密钥',
    ],
    pitfalls: [
      'kid字段暴露了租户信息 — 改用hash值，租户ID通过payload传递',
      '密钥轮换grace period内签名验证要遍历多个密钥 — 用kid直接定位，O(1)查找',
      'Redis缓存的公钥TTL和Vault轮换周期不同步 — 验证失败时主动刷新缓存重试一次',
    ],
    applicable_scenarios: '已迁移至Kong+Istio方案，此经验供参考。多租户SaaS的JWT方案仍可复用密钥轮换策略。',
    tags: [{ label: '安全', color: '#EF4444' }, { label: '认证', color: '#F59E0B' }, { label: '多租户', color: '#4A9FD8' }],
    confidence: 0.75,
    reuse_count: 2,
    projectIdx: 3,
    todoRef: { versionIdx: 0, todoIdx: 1 },
  },
];

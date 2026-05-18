export interface SeedProject {
  name: string;
  description: string;
  tech_stack: string;
  repo_url: string;
  conventions: string;
  archive?: boolean;
  versions: SeedVersion[];
}

export interface SeedVersion {
  goal: string;
  version_type: 'major' | 'minor' | 'patch';
  name?: string;
  activate?: boolean;
  release?: boolean;
  todos: SeedTodo[];
}

export interface SeedTodo {
  title: string;
  description: string;
  tags?: { label: string; color: string }[];
}

export const PROJECTS: SeedProject[] = [
  // ── 1. 成熟产品：已发布 v1.0，v1.1 进行中 ──
  {
    name: 'Arc 工作台',
    description: 'AI驱动的研发工作台，将需求从澄清到上线的全流程Pipeline化，支持多Agent编排与经验自动沉淀',
    tech_stack: 'React 19 + TypeScript + Tailwind CSS 4 / FastAPI + PostgreSQL + pgvector',
    repo_url: 'https://github.com/example/arc',
    conventions: [
      '- 前端组件使用函数式组件 + hooks，禁止 class component',
      '- API 层统一使用 ApiClient 封装，不直接调用 fetch',
      '- 后端遵循 DDD 分层：domain / application / infrastructure / interface',
      '- 所有数据库操作使用 async/await，不使用同步查询',
    ].join('\n'),
    versions: [
      {
        goal: 'MVP核心功能：项目管理、版本规划、7阶段Pipeline、AI对话、经验库',
        version_type: 'major',
        name: 'v1.0.0',
        activate: true,
        release: true,
        todos: [
          {
            title: '项目与版本CRUD',
            description: '实现项目的创建、编辑、归档、删除，以及版本的规划-激活-发布生命周期管理',
            tags: [{ label: '后端', color: '#4A9FD8' }, { label: '基础设施', color: '#888888' }],
          },
          {
            title: '7阶段Pipeline引擎',
            description: '需求澄清→UI设计→技术架构→开发→测试→部署→经验沉淀，支持阶段跳转、回退、确认',
            tags: [{ label: '核心', color: '#EF4444' }, { label: '后端', color: '#4A9FD8' }],
          },
          {
            title: 'AI对话与产出物生成',
            description: '基于LLM的多轮对话系统，按阶段上下文生成需求文档、架构方案、测试报告等产出物',
            tags: [{ label: 'AI', color: '#A78BFA' }, { label: '全栈', color: '#34D399' }],
          },
        ],
      },
      {
        goal: '响应式UI优化、多Agent接入（OpenHands/Claude Code/Codex）、经验语义搜索',
        version_type: 'minor',
        activate: true,
        todos: [
          {
            title: 'WebUI响应式布局',
            description: '适配 1024px 以下紧凑模式，侧边栏折叠为顶部导航，TodoDetail三栏布局适配移动端',
            tags: [{ label: '前端', color: '#E5A93D' }, { label: 'UI/UX', color: '#F472B6' }],
          },
          {
            title: '多Coding Agent编排层',
            description: '统一Agent适配器接口，接入OpenHands/Claude Code/Codex/Cursor，支持开发/测试/部署阶段自动执行',
            tags: [{ label: 'Agent', color: '#A78BFA' }, { label: '后端', color: '#4A9FD8' }],
          },
          {
            title: '经验库语义搜索',
            description: '基于pgvector实现经验的向量化存储与语义相似度搜索，支持按项目/个人维度过滤',
            tags: [{ label: 'AI', color: '#A78BFA' }, { label: '搜索', color: '#34D399' }],
          },
        ],
      },
    ],
  },

  // ── 2. 中期项目：v0.1 开发中，有进展 ──
  {
    name: '智能客服系统',
    description: '基于RAG的企业级智能客服平台，支持多轮对话、知识库管理、工单自动流转',
    tech_stack: 'Next.js 15 + TypeScript / Python + LangChain + Milvus + Redis',
    repo_url: 'https://github.com/example/smart-cs',
    conventions: [
      '- 使用 Server Components 优先，客户端组件标注 "use client"',
      '- RAG pipeline 中 chunk size 统一 512 tokens，overlap 64',
      '- 所有外部 API 调用需要有 retry + circuit breaker',
    ].join('\n'),
    versions: [
      {
        goal: '知识库接入、基础对话能力、工单创建',
        version_type: 'minor',
        activate: true,
        todos: [
          {
            title: '知识库文档导入与向量化',
            description: '支持PDF/Markdown/HTML文档上传，自动分块、embedding入库，支持增量更新',
            tags: [{ label: 'RAG', color: '#A78BFA' }, { label: '核心', color: '#EF4444' }],
          },
          {
            title: '多轮对话引擎',
            description: '基于LangChain构建对话链，支持上下文记忆、意图识别、知识检索增强生成',
            tags: [{ label: 'AI', color: '#A78BFA' }, { label: '后端', color: '#4A9FD8' }],
          },
          {
            title: '工单系统集成',
            description: 'AI无法解决时自动创建工单，支持转人工、工单状态追踪、满意度回收',
            tags: [{ label: '集成', color: '#E5A93D' }, { label: '后端', color: '#4A9FD8' }],
          },
          {
            title: '客服工作台前端',
            description: '客服人员操作界面：对话列表、实时聊天窗口、知识库快捷引用、客户信息侧栏',
            tags: [{ label: '前端', color: '#E5A93D' }, { label: 'UI/UX', color: '#F472B6' }],
          },
        ],
      },
    ],
  },

  // ── 3. 早期项目：刚创建，v0.1 规划中 ──
  {
    name: '数据分析平台',
    description: '面向运营团队的自助式数据分析工具，支持自然语言查询、自动生成图表和分析报告',
    tech_stack: 'Vue 3 + ECharts / Go + ClickHouse + DuckDB',
    repo_url: '',
    conventions: '',
    versions: [
      {
        goal: '自然语言转SQL、基础图表渲染、数据源接入',
        version_type: 'minor',
        todos: [
          {
            title: 'NL2SQL引擎',
            description: '将用户自然语言查询转换为SQL，支持ClickHouse/MySQL方言，包含Schema感知和查询优化',
            tags: [{ label: 'AI', color: '#A78BFA' }, { label: '核心', color: '#EF4444' }],
          },
          {
            title: '图表自动推荐与渲染',
            description: '根据查询结果自动推荐合适的图表类型（折线/柱状/饼图/散点），基于ECharts渲染',
            tags: [{ label: '前端', color: '#E5A93D' }, { label: '可视化', color: '#34D399' }],
          },
        ],
      },
    ],
  },

  // ── 4. 已归档项目 ──
  {
    name: 'Legacy API Gateway',
    description: '旧版API网关，已迁移至云原生方案(Kong + Istio)，项目归档保留文档参考',
    tech_stack: 'Node.js + Express + Nginx + Docker',
    repo_url: 'https://github.com/example/legacy-gateway',
    conventions: '',
    archive: true,
    versions: [
      {
        goal: '基础路由转发、限流、鉴权',
        version_type: 'major',
        name: 'v1.0.0',
        activate: true,
        release: true,
        todos: [
          {
            title: '路由注册与转发',
            description: '基于配置的路由表实现请求转发，支持路径重写、Header注入',
            tags: [{ label: '后端', color: '#4A9FD8' }],
          },
          {
            title: 'JWT鉴权中间件',
            description: '统一的JWT验证中间件，支持多租户token隔离',
            tags: [{ label: '安全', color: '#EF4444' }, { label: '后端', color: '#4A9FD8' }],
          },
        ],
      },
    ],
  },

  // ── 5. 设计驱动项目：v0.1已发布，v0.2进行中 ──
  {
    name: '组件设计系统',
    description: '统一的企业级UI组件库和设计Token系统，服务于所有前端项目的视觉一致性和开发效率',
    tech_stack: 'React 19 + Storybook 8 + Tailwind CSS 4 + Chromatic',
    repo_url: 'https://github.com/example/design-system',
    conventions: [
      '- 所有组件需提供 Storybook story 和 Chromatic 视觉回归快照',
      '- Design Token 使用 CSS Custom Properties，不硬编码颜色/间距值',
      '- 组件 API 设计遵循 WAI-ARIA 无障碍标准',
      '- 每个组件必须有 unit test 覆盖核心交互逻辑',
    ].join('\n'),
    versions: [
      {
        goal: '基础组件库：Button/Input/Select/Modal/Toast/Table',
        version_type: 'minor',
        name: 'v0.1.0',
        activate: true,
        release: true,
        todos: [
          {
            title: 'Design Token 体系',
            description: '定义颜色、字体、间距、圆角、阴影等Token，支持亮/暗主题切换',
            tags: [{ label: '设计', color: '#F472B6' }, { label: '基础', color: '#888888' }],
          },
          {
            title: '表单组件集',
            description: 'Button/Input/Select/Checkbox/Radio/Switch，统一的交互反馈和验证状态',
            tags: [{ label: '组件', color: '#34D399' }, { label: '前端', color: '#E5A93D' }],
          },
        ],
      },
      {
        goal: '复合组件：DataTable/DatePicker/Drawer/Command Palette',
        version_type: 'minor',
        activate: true,
        todos: [
          {
            title: 'DataTable 高性能表格',
            description: '支持虚拟滚动、列排序/筛选/固定、行选择、自适应列宽，10万行数据流畅渲染',
            tags: [{ label: '组件', color: '#34D399' }, { label: '性能', color: '#EF4444' }],
          },
          {
            title: 'Command Palette 命令面板',
            description: '全局快捷键唤起，支持模糊搜索、快捷操作、最近使用记录，类似 VS Code Ctrl+Shift+P',
            tags: [{ label: '组件', color: '#34D399' }, { label: 'UX', color: '#F472B6' }],
          },
          {
            title: 'DatePicker 日期选择器',
            description: '单日/日期范围选择，支持快捷选项（今天/本周/本月），国际化日期格式',
            tags: [{ label: '组件', color: '#34D399' }],
          },
        ],
      },
    ],
  },
];

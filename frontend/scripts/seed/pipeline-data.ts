import type { SeedProject } from './data';

export interface PipelineData {
  phase_type: string;
  status: 'pending' | 'active' | 'awaiting_confirm' | 'confirmed' | 'skipped';
  messages?: { role: 'user' | 'assistant' | 'system'; content: string }[];
  artifact?: { artifact_type: string; content: Record<string, unknown>; is_confirmed: boolean };
}

export function buildPipeline(todoTitle: string, todoDescription: string, projectName: string): PipelineData[] {
  return [
    {
      phase_type: 'clarification',
      status: 'confirmed',
      messages: [
        { role: 'system', content: `正在进行需求澄清阶段。需求：${todoTitle}` },
        { role: 'user', content: todoDescription },
        { role: 'assistant', content: `我来梳理一下这个需求的核心要点：\n\n**目标**: ${todoTitle}\n\n**用户场景**: 项目 ${projectName} 的开发团队需要实现此功能。\n\n让我生成需求规格文档，请确认。` },
        { role: 'user', content: '确认，请生成需求文档' },
      ],
      artifact: {
        artifact_type: 'requirement_spec',
        is_confirmed: true,
        content: {
          background: `在 ${projectName} 项目中，团队需要实现「${todoTitle}」功能。${todoDescription}`,
          user_scenarios: `1. 开发者在本地环境中使用该功能进行日常开发\n2. 团队成员通过代码评审验证实现质量\n3. 产品经理通过验收标准确认功能符合预期`,
          goals: `- 核心功能完整可用\n- 代码质量符合项目规范\n- 有充分的测试覆盖\n- 文档完善，便于后续维护`,
          boundaries: `- 不涉及非本期规划的功能扩展\n- 不改变已有接口的兼容性\n- 性能指标需满足生产环境要求`,
          acceptance_criteria: `- [ ] 功能按设计实现，核心流程可走通\n- [ ] 单元测试覆盖率 > 80%\n- [ ] 代码通过 lint 检查和类型检查\n- [ ] 文档更新完毕`,
          risk_assessment: `- 与已有模块的耦合度需要评估\n- 数据迁移方案需提前验证\n- 并发场景下的一致性保证`,
        },
      },
    },
    {
      phase_type: 'ui_design',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在进行UI设计阶段' },
        { role: 'assistant', content: `基于需求文档，我为「${todoTitle}」设计了页面流程和交互方案。包含用户流程图、页面线框和组件规格。` },
        { role: 'user', content: '设计方案可以，确认通过' },
      ],
      artifact: {
        artifact_type: 'ui_design',
        is_confirmed: true,
        content: {
          flow_diagram: `graph TD\n  A[用户进入] --> B{选择操作}\n  B -->|创建| C[填写表单]\n  B -->|查看| D[列表展示]\n  C --> E[提交验证]\n  E -->|成功| F[跳转详情]\n  E -->|失败| G[显示错误]\n  D --> H[搜索/筛选]\n  H --> I[查看详情]`,
          wireframes: [
            {
              page_name: '列表页',
              description: '展示所有条目，支持搜索和筛选',
              html: '<div style="border:1px solid #ccc;padding:16px;font-family:sans-serif;background:#f5f5f5"><div style="display:flex;justify-content:space-between;margin-bottom:12px"><h3 style="margin:0">列表</h3><button style="padding:4px 12px;background:#4A9FD8;color:white;border:none;border-radius:4px">+ 新建</button></div><input style="width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;margin-bottom:8px" placeholder="搜索..."/><div style="border:1px solid #eee;border-radius:4px;padding:12px;margin-bottom:8px;background:white">条目 1</div><div style="border:1px solid #eee;border-radius:4px;padding:12px;background:white">条目 2</div></div>',
            },
          ],
          component_specs: [
            { name: '搜索栏', purpose: '关键词过滤', behavior: '输入时防抖 400ms 触发搜索', states: '空态 / 加载中 / 有结果 / 无结果' },
            { name: '操作按钮组', purpose: '条目操作', behavior: '点击展开下拉菜单', states: '默认 / hover / 展开' },
          ],
          interaction_rules: '- 列表支持无限滚动加载\n- 操作确认使用二次确认弹窗\n- 成功/失败使用 Toast 反馈',
          responsive_notes: '- 小屏下搜索栏与按钮堆叠\n- 卡片网格自适应列数\n- 侧栏在移动端折叠为底部 Tab',
        },
      },
    },
    {
      phase_type: 'architecture',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在进行技术架构设计阶段' },
        { role: 'assistant', content: `为「${todoTitle}」制定技术方案。采用分层架构，确保可维护性和可测试性。` },
        { role: 'user', content: '架构方案确认' },
      ],
      artifact: {
        artifact_type: 'tech_architecture',
        is_confirmed: true,
        content: {
          architecture_overview: `采用前后端分离架构：\n\n**前端**: React + TypeScript，组件化开发，状态使用 hooks 管理\n\n**后端**: FastAPI + SQLAlchemy，DDD分层设计\n\n**存储**: PostgreSQL 主库 + Redis 缓存\n\n**通信**: RESTful API + WebSocket (实时推送)`,
          data_model: `-- 核心表结构\nCREATE TABLE items (\n  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),\n  title VARCHAR(200) NOT NULL,\n  status VARCHAR(20) NOT NULL DEFAULT 'active',\n  metadata JSONB DEFAULT '{}',\n  created_at TIMESTAMPTZ DEFAULT NOW(),\n  updated_at TIMESTAMPTZ DEFAULT NOW()\n);\n\nCREATE INDEX idx_items_status ON items(status);\nCREATE INDEX idx_items_created ON items(created_at DESC);`,
          api_design: `# API 端点设计\n\nGET    /api/items          -- 列表查询 (分页+筛选)\nPOST   /api/items          -- 创建\nGET    /api/items/:id      -- 详情\nPATCH  /api/items/:id      -- 更新\nDELETE /api/items/:id      -- 删除\nPOST   /api/items/:id/action -- 状态变更`,
          tech_decisions: [
            { decision: '状态管理方案', options: 'Redux / Zustand / React Context', chosen: 'React Hooks + Context', reason: '项目规模适中，无需引入额外状态库' },
            { decision: '数据库选型', options: 'PostgreSQL / MySQL / MongoDB', chosen: 'PostgreSQL', reason: '支持 JSONB、全文搜索、pgvector 扩展' },
            { decision: 'API 风格', options: 'REST / GraphQL / tRPC', chosen: 'RESTful', reason: '团队熟悉度高，工具链成熟' },
          ],
          implementation_plan: `**Phase 1** (2天): 数据模型 + API 骨架\n**Phase 2** (3天): 核心业务逻辑 + 单元测试\n**Phase 3** (2天): 前端页面 + 集成测试\n**Phase 4** (1天): 性能优化 + 部署配置`,
        },
      },
    },
    {
      phase_type: 'development',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在执行开发阶段' },
        { role: 'assistant', content: `开发完成。代码已提交至仓库，所有测试通过。\n\n主要变更：\n- 新增 3 个 API 端点\n- 新增 2 个前端页面组件\n- 编写 12 个单元测试\n\n代码覆盖率: 85%` },
      ],
      artifact: {
        artifact_type: 'dev_report',
        is_confirmed: true,
        content: {
          execution_log: `[Agent: Claude Code]\n$ git checkout -b feature/${slugify(todoTitle)}\nSwitched to a new branch\n\n$ Creating backend models and routes...\n✓ Created src/models/item.py\n✓ Created src/routes/item.py\n✓ Created src/services/item_service.py\n\n$ Creating frontend components...\n✓ Created src/pages/ItemList.tsx\n✓ Created src/components/ItemCard.tsx\n\n$ Running tests...\n✓ 12 tests passed, 0 failed\n✓ Coverage: 85.2%\n\n$ git commit -m "feat: implement ${todoTitle}"\n[feature branch abc1234] feat: implement ${todoTitle}`,
          code_changes: [
            `新增 src/models/item.py — 数据模型定义`,
            `新增 src/routes/item.py — API 路由 (CRUD + 状态变更)`,
            `新增 src/services/item_service.py — 业务逻辑层`,
            `新增 src/pages/ItemList.tsx — 列表页面组件`,
            `新增 src/components/ItemCard.tsx — 卡片组件`,
            `修改 src/main.py — 注册新路由`,
          ],
          test_results: `测试套件: 3 个文件\n总计: 12 个测试\n通过: 12 ✓\n失败: 0\n覆盖率: 85.2%\n\n详情:\n  test_item_crud.py .............. 5 passed\n  test_item_service.py ........... 4 passed\n  test_item_api.py ............... 3 passed`,
          decisions_made: [
            { decision: '使用乐观锁处理并发更新', reason: '避免数据库行锁导致的性能瓶颈，业务场景冲突概率低' },
            { decision: '列表接口使用游标分页', reason: '深度翻页场景下 offset 性能衰减，cursor 更稳定' },
          ],
        },
      },
    },
    {
      phase_type: 'testing',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在执行测试验证阶段' },
        { role: 'assistant', content: '测试完成。所有验收标准通过，发现 1 个低优先级问题已记录。' },
      ],
      artifact: {
        artifact_type: 'test_report',
        is_confirmed: true,
        content: {
          criteria_verification: [
            { criteria: '功能按设计实现，核心流程可走通', status: 'pass', evidence: '手动验证创建/查询/更新/删除全流程正常' },
            { criteria: '单元测试覆盖率 > 80%', status: 'pass', evidence: '当前覆盖率 85.2%，超过阈值' },
            { criteria: '代码通过 lint 检查和类型检查', status: 'pass', evidence: 'eslint + tsc --noEmit 均通过' },
            { criteria: '文档更新完毕', status: 'pass', evidence: 'API 文档已自动生成，README 已更新' },
          ],
          issues_found: [
            { description: '列表空态时占位图尺寸在 Safari 下偏大', severity: 'low', suggestion: '添加 max-width 约束，非阻塞问题可后续修复' },
          ],
          coverage_summary: '总覆盖率: 85.2%\n- 行覆盖: 87.1%\n- 分支覆盖: 78.3%\n- 函数覆盖: 92.0%\n\n未覆盖区域主要集中在错误处理的边缘分支，不影响核心逻辑。',
        },
      },
    },
    {
      phase_type: 'deployment',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在执行部署阶段' },
        { role: 'assistant', content: '部署完成。服务已上线，健康检查通过。' },
      ],
      artifact: {
        artifact_type: 'deploy_report',
        is_confirmed: true,
        content: {
          deploy_log: `$ docker build -t app:latest .\nSuccessfully built 8a2f3e4c\n\n$ docker push registry.example.com/app:latest\nPushed successfully\n\n$ kubectl apply -f k8s/deployment.yaml\ndeployment.apps/app configured\nservice/app unchanged\n\n$ kubectl rollout status deployment/app\ndeployment "app" successfully rolled out\n\nPods: 3/3 Running\nRevision: 12`,
          service_url: 'https://app.example.com',
          health_check_result: 'OK — All endpoints healthy (response time < 50ms)',
          rollback_plan: '如需回滚:\n```\nkubectl rollout undo deployment/app\n```\n\n回滚后需手动验证:\n1. 检查 /health 端点\n2. 确认数据库迁移兼容\n3. 通知相关方',
        },
      },
    },
    {
      phase_type: 'extraction',
      status: 'confirmed',
      messages: [
        { role: 'system', content: '正在进行经验沉淀阶段' },
        { role: 'assistant', content: '已从本次开发中提取经验卡片，包含关键决策和踩坑记录。' },
      ],
      artifact: {
        artifact_type: 'experience_card',
        is_confirmed: true,
        content: {
          problem: `在实现「${todoTitle}」时，需要解决的核心挑战是：如何在保证代码质量的前提下高效完成功能开发。`,
          solution: `采用 DDD 分层架构 + TDD 开发流程：先写测试再实现，确保每一层职责清晰、可独立测试。`,
          decisions: [
            { point: '并发控制策略', chosen: '乐观锁 (version字段)', reason: '低冲突场景下性能优于悲观锁' },
            { point: '分页方案', chosen: 'Cursor-based', reason: '万级数据量下性能稳定，不受深度翻页影响' },
          ],
          pitfalls: [
            { issue: 'TypeScript 严格模式下 JSONB 字段类型推断', cause: 'SQLAlchemy 返回的 dict 与 TS interface 不自动匹配', fix: '定义专门的 Zod schema 做运行时验证' },
            { issue: 'React 18 并发模式下重复请求', cause: 'StrictMode 导致 useEffect 执行两次', fix: '使用 AbortController 取消重复请求' },
          ],
          applicable_scenarios: '适用于所有需要 CRUD + 状态管理的业务模块开发，特别是数据量中等 (万级)、读多写少的场景。',
          tags: ['DDD', '乐观锁', 'Cursor分页', 'TypeScript', 'React'],
        },
      },
    },
  ];
}

function slugify(s: string): string {
  return s.replace(/[^a-zA-Z0-9一-龥]/g, '-').slice(0, 30).toLowerCase();
}

// Partial pipeline for "in progress" todos — only some phases done
export function buildPartialPipeline(todoTitle: string, todoDescription: string, projectName: string, upToPhase: string): PipelineData[] {
  const full = buildPipeline(todoTitle, todoDescription, projectName);
  const phaseOrder = ['clarification', 'ui_design', 'architecture', 'development', 'testing', 'deployment', 'extraction'];
  const targetIdx = phaseOrder.indexOf(upToPhase);

  return full.map((phase, i) => {
    if (i < targetIdx) {
      return phase; // confirmed
    } else if (i === targetIdx) {
      return { ...phase, status: 'active' as const }; // currently active
    } else {
      return { phase_type: phase.phase_type, status: 'pending' as const }; // not yet started
    }
  });
}

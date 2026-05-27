"""Seed artifact data constants — pure data, exempt from line limits."""

TODO1_REQUIREMENT_SPEC = {
    "background": (
        "运营团队每月需要从系统中导出用户行为数据用于分析报告，"
        "目前只能通过数据库直连手动查询导出，效率低且存在安全风险。"
        "需要在后台管理系统中提供自助化的批量数据导出功能。"
    ),
    "user_scenarios": (
        "1. 管理员登录后台，进入「数据导出」页面\n"
        "2. 选择数据类型（用户行为/订单/商品），设置日期范围和筛选条件\n"
        "3. 点击「预览」查看前20条数据确认格式\n"
        "4. 点击「导出」，系统后台异步生成CSV文件\n"
        "5. 导出完成后通知管理员，可在「导出历史」页面下载"
    ),
    "goals": (
        "- 支持10万行级别的数据导出，5分钟内完成\n"
        "- 支持按日期范围、用户类型、地区等维度筛选\n"
        "- CSV格式正确，支持中文和特殊字符\n"
        "- 导出历史可追溯，保留最近30天的导出记录"
    ),
    "boundaries": (
        "- 本期不支持自定义列选择（v2考虑）\n"
        "- 不做实时流式下载，采用异步任务+通知方式\n"
        "- 不支持Excel格式（仅CSV）\n"
        "- 单次导出上限50万行"
    ),
    "acceptance_criteria": (
        "1. 导出10万行数据耗时 < 5分钟\n"
        "2. CSV文件可被Excel正确打开，中文无乱码\n"
        "3. 并发导出（同时3个任务）系统稳定\n"
        "4. 导出失败有明确错误提示和重试机制\n"
        "5. 导出记录保留30天，支持重新下载"
    ),
    "risk_assessment": (
        "- 大数据量可能OOM：采用流式写入，分批查询（每批5000行）\n"
        "- 并发导出占用资源：使用任务队列控制并发数（最多3个）\n"
        "- CSV注入攻击：对以=、+、-、@开头的单元格内容做转义\n"
        "- 文件存储空间：定时清理30天前的文件"
    ),
}


TODO1_UI_DESIGN = {
    "flow_diagram": (
        "graph TD\n"
        "    A[管理员登录后台] --> B[进入数据导出页面]\n"
        "    B --> C[选择数据类型]\n"
        "    C --> D[设置筛选条件]\n"
        "    D --> E[日期范围选择]\n"
        "    D --> F[用户类型筛选]\n"
        "    D --> G[地区筛选]\n"
        "    E & F & G --> H[点击预览]\n"
        "    H --> I{数据量检查}\n"
        "    I -->|≤50万行| J[显示前20条预览]\n"
        "    I -->|>50万行| K[提示缩小范围]\n"
        "    K --> D\n"
        "    J --> L[确认导出]\n"
        "    L --> M[提交异步任务]\n"
        "    M --> N[任务排队/执行中]\n"
        "    N --> O{导出结果}\n"
        "    O -->|成功| P[通知 + 下载链接]\n"
        "    O -->|失败| Q[错误提示 + 重试]\n"
        "    Q --> L\n"
        "    P --> R[导出历史页面下载]"
    ),
    "wireframes": [
        {
            "page_name": "数据导出配置页",
            "description": "用户在此页面选择数据类型、设置筛选条件、预览数据、发起导出",
            "html": (
                '<div class="min-h-screen bg-gray-900 p-6">'
                '<div class="max-w-4xl mx-auto">'
                '<h1 class="text-xl font-bold text-white mb-6">数据导出</h1>'
                '<div class="bg-gray-800 rounded-lg p-5 mb-4">'
                '<h2 class="text-sm font-medium text-gray-400 mb-3">数据类型</h2>'
                '<div class="flex gap-3">'
                '<button class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">用户行为</button>'
                '<button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md text-sm">订单数据</button>'
                '<button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md text-sm">商品数据</button>'
                "</div></div>"
                '<div class="bg-gray-800 rounded-lg p-5 mb-4">'
                '<h2 class="text-sm font-medium text-gray-400 mb-3">筛选条件</h2>'
                '<div class="grid grid-cols-2 gap-4">'
                '<div><label class="block text-xs text-gray-500 mb-1">开始日期</label>'
                '<input type="date" value="2026-04-01" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /></div>'
                '<div><label class="block text-xs text-gray-500 mb-1">结束日期</label>'
                '<input type="date" value="2026-04-30" class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white" /></div>'
                '<div><label class="block text-xs text-gray-500 mb-1">用户类型</label>'
                '<select class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white"><option>全部</option><option>付费用户</option></select></div>'
                '<div><label class="block text-xs text-gray-500 mb-1">地区</label>'
                '<select class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-white"><option>全部</option><option>华东</option></select></div>'
                "</div></div>"
                '<div class="bg-gray-800 rounded-lg p-5 mb-4">'
                '<div class="flex items-center justify-between mb-3">'
                '<h2 class="text-sm font-medium text-gray-400">数据预览 <span class="text-indigo-400">(匹配 87,432 条)</span></h2></div>'
                '<div class="overflow-x-auto"><table class="w-full text-left text-xs">'
                '<thead><tr class="border-b border-gray-700 text-gray-500">'
                '<th class="pb-2 pr-4">用户ID</th><th class="pb-2 pr-4">行为类型</th>'
                '<th class="pb-2 pr-4">页面路径</th><th class="pb-2 pr-4">时间</th><th class="pb-2">设备</th></tr></thead>'
                '<tbody class="text-gray-300">'
                '<tr class="border-b border-gray-800"><td class="py-2 pr-4 font-mono">u_38a21</td>'
                '<td class="py-2 pr-4">页面浏览</td><td class="py-2 pr-4">/products/list</td>'
                '<td class="py-2 pr-4">2026-04-15 09:32</td><td class="py-2">iOS</td></tr>'
                '<tr><td class="py-2 pr-4 font-mono">u_7bc43</td>'
                '<td class="py-2 pr-4">按钮点击</td><td class="py-2 pr-4">/cart/checkout</td>'
                '<td class="py-2 pr-4">2026-04-15 09:33</td><td class="py-2">Android</td></tr>'
                "</tbody></table></div>"
                '<p class="mt-2 text-xs text-gray-600">显示前 2 条 / 共 87,432 条</p></div>'
                '<div class="flex items-center justify-between">'
                '<p class="text-xs text-gray-500">预计文件大小: ~12.3 MB  |  预计耗时: ~2 分钟</p>'
                '<button class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium">确认导出</button>'
                "</div></div></div>"
            ),
        },
        {
            "page_name": "导出历史页",
            "description": "展示历史导出记录、状态、下载链接",
            "html": (
                '<div class="min-h-screen bg-gray-900 p-6">'
                '<div class="max-w-4xl mx-auto">'
                '<h1 class="text-xl font-bold text-white mb-6">导出历史</h1>'
                '<div class="bg-gray-800 rounded-lg overflow-hidden">'
                '<table class="w-full text-left text-sm">'
                '<thead><tr class="border-b border-gray-700 text-xs text-gray-500 uppercase">'
                '<th class="px-5 py-3">数据类型</th><th class="px-5 py-3">筛选条件</th>'
                '<th class="px-5 py-3">数据量</th><th class="px-5 py-3">状态</th>'
                '<th class="px-5 py-3">操作</th></tr></thead>'
                '<tbody class="text-gray-300">'
                '<tr class="border-b border-gray-800/50"><td class="px-5 py-3">用户行为</td>'
                '<td class="px-5 py-3 text-xs text-gray-400">2026-04-01 ~ 04-30 | 付费用户</td>'
                '<td class="px-5 py-3">87,432</td>'
                '<td class="px-5 py-3"><span class="text-green-400 text-xs">完成</span></td>'
                '<td class="px-5 py-3"><button class="text-indigo-400 text-xs">下载</button></td></tr>'
                '<tr><td class="px-5 py-3">订单数据</td>'
                '<td class="px-5 py-3 text-xs text-gray-400">2026-03-01 ~ 03-31</td>'
                '<td class="px-5 py-3">23,891</td>'
                '<td class="px-5 py-3"><span class="text-yellow-400 text-xs">导出中...</span></td>'
                '<td class="px-5 py-3"><span class="text-gray-600 text-xs">—</span></td></tr>'
                "</tbody></table></div></div></div>"
            ),
        },
    ],
    "component_specs": [
        {
            "name": "DataTypeSelector",
            "purpose": "数据类型切换",
            "behavior": "点击切换，高亮选中项",
            "states": "default / selected / disabled",
        },
        {
            "name": "FilterPanel",
            "purpose": "筛选条件面板",
            "behavior": "修改条件后刷新预览",
            "states": "default / loading / error",
        },
        {
            "name": "DataPreview",
            "purpose": "数据预览表格",
            "behavior": "显示前20条和总数",
            "states": "empty / loading / loaded / over-limit",
        },
        {
            "name": "ExportButton",
            "purpose": "触发异步导出",
            "behavior": "确认后提交任务",
            "states": "default / loading / disabled",
        },
        {
            "name": "ExportHistoryTable",
            "purpose": "历史导出记录",
            "behavior": "按时间倒序，支持下载/重试",
            "states": "empty / loaded",
        },
    ],
    "interaction_rules": (
        "1. 筛选条件变化后，防抖500ms再触发预览刷新\n"
        "2. 导出确认弹窗显示预估文件大小和耗时\n"
        "3. 导出中禁止修改当前配置\n"
        "4. 导出完成通过 WebSocket 推送通知\n"
        "5. 失败时显示错误原因，提供「重试」操作"
    ),
    "responsive_notes": "桌面端后台，最小支持宽度1024px。筛选条件窄屏下1列。预览表格横向滚动。",
}


TODO2_REQUIREMENT_SPEC = {
    "background": (
        "后台管理系统无权限控制，所有登录用户可执行任何操作。运营人员曾误删导出配置，"
        "数据安全审计要求必须做权限隔离。需要基于角色的访问控制体系。"
    ),
    "user_scenarios": (
        "1. 管理员登录后台，进入「用户管理」页面，查看所有用户列表\n"
        "2. 管理员修改用户角色（管理员→运营），保存后立即生效\n"
        "3. 运营人员登录后，侧边栏不显示「系统配置」入口\n"
        "4. 运营人员可正常使用导出和看板功能\n"
        "5. 只读用户登录后仅看到看板入口，导出按钮不可见"
    ),
    "goals": (
        "- 三种固定角色：管理员 / 运营 / 只读\n"
        "- 各页面根据角色控制可见性和可操作性\n"
        "- 越权操作后端返回403，前端隐藏不可用功能\n"
        "- 登录态过期自动跳转登录页"
    ),
    "boundaries": (
        "- 不支持自定义角色（固定三种即可）\n"
        "- 不做数据级权限隔离（运营可看所有数据）\n"
        "- 一个用户只能有一个角色"
    ),
    "acceptance_criteria": (
        "1. 管理员可执行所有操作，包括用户管理\n"
        "2. 运营可导出数据、查看看板，不可修改系统配置\n"
        "3. 只读用户仅可查看看板\n"
        "4. 越权API调用返回403\n"
        "5. access_token 30分钟过期，refresh_token 7天"
    ),
    "risk_assessment": (
        "- JWT过期处理不当导致体验差：前端axios拦截器静默刷新\n"
        "- 权限绕过风险：后端中间件作为权威层，前端只做展示层适配\n"
        "- 角色变更后旧token仍有效：接受此风险，最多30分钟延迟"
    ),
}


TODO2_UI_DESIGN = {
    "flow_diagram": (
        "graph TD\n"
        "    A[用户登录] --> B{角色判断}\n"
        "    B -->|管理员| C[完整侧边栏]\n"
        "    B -->|运营| D[隐藏配置入口]\n"
        "    B -->|只读| E[仅看板入口]\n"
        "    C --> F[用户管理页]\n"
        "    F --> G[查看用户列表]\n"
        "    G --> H[修改角色]\n"
        "    G --> I[禁用账号]\n"
        "    F --> J[新增用户]\n"
        "    D --> K[数据导出]\n"
        "    D --> L[查看看板]\n"
        "    E --> L"
    ),
    "wireframes": [
        {
            "page_name": "用户管理页",
            "description": "管理员专属，管理用户账号和角色分配",
            "html": (
                '<div class="min-h-screen bg-gray-900 p-6">'
                '<div class="max-w-5xl mx-auto">'
                '<div class="flex items-center justify-between mb-6">'
                '<h1 class="text-xl font-bold text-white">用户管理</h1>'
                '<button class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">新增用户</button>'
                "</div>"
                '<div class="bg-gray-800 rounded-lg overflow-hidden">'
                '<table class="w-full text-left text-sm">'
                '<thead><tr class="border-b border-gray-700 text-xs text-gray-500 uppercase">'
                '<th class="px-5 py-3">用户名</th><th class="px-5 py-3">显示名</th>'
                '<th class="px-5 py-3">角色</th><th class="px-5 py-3">状态</th>'
                '<th class="px-5 py-3">操作</th></tr></thead>'
                '<tbody class="text-gray-300">'
                '<tr class="border-b border-gray-800/50"><td class="px-5 py-3 font-mono">admin</td>'
                '<td class="px-5 py-3">系统管理员</td>'
                '<td class="px-5 py-3"><span class="px-2 py-1 bg-red-900/30 text-red-400 rounded text-xs">管理员</span></td>'
                '<td class="px-5 py-3"><span class="text-green-400 text-xs">启用</span></td>'
                '<td class="px-5 py-3 text-xs text-gray-500">—</td></tr>'
                '<tr class="border-b border-gray-800/50"><td class="px-5 py-3 font-mono">zhang_ops</td>'
                '<td class="px-5 py-3">张运营</td>'
                '<td class="px-5 py-3"><span class="px-2 py-1 bg-blue-900/30 text-blue-400 rounded text-xs">运营</span></td>'
                '<td class="px-5 py-3"><span class="text-green-400 text-xs">启用</span></td>'
                '<td class="px-5 py-3"><button class="text-indigo-400 text-xs mr-3">编辑</button><button class="text-red-400 text-xs">禁用</button></td></tr>'
                '<tr><td class="px-5 py-3 font-mono">li_view</td>'
                '<td class="px-5 py-3">李主管</td>'
                '<td class="px-5 py-3"><span class="px-2 py-1 bg-gray-700 text-gray-400 rounded text-xs">只读</span></td>'
                '<td class="px-5 py-3"><span class="text-green-400 text-xs">启用</span></td>'
                '<td class="px-5 py-3"><button class="text-indigo-400 text-xs mr-3">编辑</button><button class="text-red-400 text-xs">禁用</button></td></tr>'
                "</tbody></table></div></div></div>"
            ),
        },
    ],
    "component_specs": [
        {
            "name": "UserTable",
            "purpose": "用户列表",
            "behavior": "展示用户信息，支持角色编辑和状态切换",
            "states": "empty / loaded / loading",
        },
        {
            "name": "RoleBadge",
            "purpose": "角色标签",
            "behavior": "根据角色显示不同颜色",
            "states": "admin(red) / operator(blue) / readonly(gray)",
        },
        {
            "name": "AddUserModal",
            "purpose": "新增用户弹窗",
            "behavior": "输入用户名+密码+角色，提交创建",
            "states": "default / validating / error",
        },
        {
            "name": "PermissionGuard",
            "purpose": "权限守卫组件",
            "behavior": "根据当前用户角色决定子元素是否渲染",
            "states": "visible / hidden",
        },
    ],
    "interaction_rules": (
        "1. 不可修改自己的角色\n"
        "2. 不可禁用自己的账号\n"
        "3. 角色修改需要二次确认弹窗\n"
        "4. 禁用账号后该用户立即被强制下线（token失效）"
    ),
    "responsive_notes": "桌面端后台，最小支持宽度1024px。用户表格横向滚动。",
}


TODO2_TECH_ARCHITECTURE = {
    "architecture_overview": (
        "基于 JWT + RBAC 的前后端双重权限控制体系，后端作为权威层，前端做展示层适配。\n\n"
        "三层架构：\n"
        "1. 认证层 (Authentication) — JWT token 签发与验证\n"
        "   - 登录成功签发 access_token(30min) + refresh_token(7d)\n"
        "   - access_token payload: {user_id, username, role, exp}\n"
        "   - FastAPI Dependency: get_current_user 解析 Authorization header\n\n"
        "2. 鉴权层 (Authorization) — 角色-权限映射与中间件\n"
        "   - 角色定义：admin / operator / readonly\n"
        "   - 权限硬编码在 ROLE_PERMISSIONS 常量中\n"
        "   - @require_role('admin') 装饰器保护敏感接口\n\n"
        "3. 前端适配层 — 路由守卫与组件级权限控制\n"
        "   - AuthContext 存储登录状态和角色\n"
        "   - ProtectedRoute 组件做路由级拦截\n"
        "   - usePermission hook 做按钮级控制\n"
        "   - axios 拦截器处理 401 → 自动 refresh → 重试"
    ),
    "data_model": (
        "users 表:\n"
        "  - id: UUID PK\n"
        "  - username: VARCHAR(100) UNIQUE\n"
        "  - hashed_password: TEXT\n"
        "  - display_name: VARCHAR(200)\n"
        "  - role: VARCHAR(20) DEFAULT 'readonly'\n"
        "  - is_active: BOOLEAN DEFAULT true\n\n"
        "ROLE_PERMISSIONS 常量映射:\n"
        "  admin: ['*']\n"
        "  operator: ['export:read', 'export:create', 'dashboard:read']\n"
        "  readonly: ['dashboard:read']"
    ),
    "api_design": (
        "POST /api/auth/login → {access_token, refresh_token, user}\n"
        "POST /api/auth/refresh → {access_token}\n"
        "GET /api/auth/me → {user_info}\n"
        "GET /api/users → 用户列表 [admin only]\n"
        "PATCH /api/users/:id/role → 修改角色 [admin only]\n"
        "PATCH /api/users/:id/status → 启用/禁用 [admin only]"
    ),
    "tech_decisions": [
        {
            "decision": "角色-权限映射方式",
            "chosen": "硬编码常量",
            "reason": "三种固定角色，不需要动态配置的灵活性，代码量减少70%",
        },
        {
            "decision": "会话管理方案",
            "chosen": "JWT 而非 Session",
            "reason": "前后端分离架构，无需服务端存储会话状态",
        },
        {
            "decision": "Token 过期策略",
            "chosen": "access_token 30min + refresh_token 7d",
            "reason": "平衡安全性和用户体验，短token减少泄露窗口",
        },
    ],
    "implementation_plan": (
        "Phase 1: 后端鉴权基础 (2天)\n"
        "  - JWT签发/验证 + get_current_user dependency\n"
        "  - ROLE_PERMISSIONS 常量 + require_role 装饰器\n\n"
        "Phase 2: 用户管理接口 (1天)\n"
        "  - CRUD接口 + 角色变更逻辑\n\n"
        "Phase 3: 前端适配 (2天)\n"
        "  - AuthContext + ProtectedRoute + axios拦截器\n"
        "  - 用户管理页面\n\n"
        "风险: 角色变更后旧token仍有效（最多30min延迟）—— 可接受的安全妥协"
    ),
}


TODO2_DEV_REPORT = {
    "execution_log": (
        "$ alembic upgrade head\n"
        "INFO  [alembic.runtime.migration] Running upgrade -> add_users_role_field\n"
        "INFO  [alembic.runtime.migration] Migration complete\n\n"
        "$ pytest tests/auth/ -v\n"
        "tests/auth/test_login.py::test_login_success PASSED\n"
        "tests/auth/test_login.py::test_wrong_password PASSED\n"
        "tests/auth/test_login.py::test_user_not_found PASSED\n"
        "tests/auth/test_refresh.py::test_refresh_success PASSED\n"
        "tests/auth/test_refresh.py::test_expired_refresh PASSED\n"
        "tests/auth/test_rbac.py::test_admin_access PASSED\n"
        "tests/auth/test_rbac.py::test_operator_forbidden PASSED\n"
        "tests/auth/test_rbac.py::test_readonly_forbidden PASSED\n"
        "...\n"
        "27 passed in 4.32s\n\n"
        "$ npm run build\n"
        "vite v5.x building for production...\n"
        "✓ 142 modules transformed.\n"
        "dist/index.html    0.45 kB │ gzip:  0.29 kB\n"
        "dist/assets/index-Dk3f8.js  186.23 kB │ gzip: 58.41 kB\n"
        "✓ built in 3.21s"
    ),
    "code_changes": [
        "backend/src/arc/application/auth/service.py — JWT签发与验证逻辑",
        "backend/src/arc/application/auth/password.py — bcrypt密码哈希",
        "backend/src/arc/interface/deps.py — get_current_user dependency注入",
        "backend/src/arc/interface/routes/auth.py — 登录/注册/刷新接口",
        "backend/src/arc/infrastructure/models/user.py — 用户ORM模型",
        "frontend/src/contexts/AuthContext.tsx — 认证上下文Provider",
        "frontend/src/pages/LoginPage.tsx — 登录页面",
        "frontend/src/components/ProtectedRoute.tsx — 路由权限守卫",
    ],
    "test_results": "27/27 tests passed | Line coverage: 89.2% | Branch coverage: 76.5% | Duration: 4.32s",
    "decisions_made": [
        {
            "decision": "使用 Promise 锁处理并发 refresh",
            "reason": "避免多个401请求同时触发refresh导致竞态条件",
        },
        {
            "decision": "权限映射硬编码在常量中",
            "reason": "三种固定角色变更频率极低，数据库方案引入不必要的复杂度",
        },
        {
            "decision": "前端 axios 拦截器统一处理 401",
            "reason": "避免每个API调用都手动处理token过期逻辑",
        },
    ],
}


TODO2_TEST_REPORT = {
    "criteria_verification": [
        {
            "criteria": "管理员可执行所有操作，包括用户管理",
            "status": "pass",
            "evidence": "admin角色通过所有接口测试（12/12），包括用户CRUD和角色变更",
        },
        {
            "criteria": "运营可导出数据、查看看板，不可修改系统配置",
            "status": "pass",
            "evidence": "operator角色导出和看板接口返回200，用户管理和配置接口返回403",
        },
        {
            "criteria": "只读用户仅可查看看板",
            "status": "pass",
            "evidence": "readonly角色仅看板接口200，导出和配置接口均返回403",
        },
        {
            "criteria": "越权API调用返回403",
            "status": "pass",
            "evidence": "所有越权场景均返回403 Forbidden，响应体包含具体权限缺失信息",
        },
        {
            "criteria": "access_token 30分钟过期，refresh_token 7天",
            "status": "pass",
            "evidence": "token过期后返回401，refresh成功续期，过期refresh返回401并跳转登录",
        },
    ],
    "issues_found": [
        {
            "description": "并发refresh请求偶发竞态",
            "severity": "medium",
            "suggestion": "已通过Promise锁修复，建议增加并发场景的E2E测试覆盖",
        },
        {
            "description": "角色变更后旧token仍有效",
            "severity": "low",
            "suggestion": "设计决策：接受最多30分钟延迟，无需修复",
        },
    ],
    "coverage_summary": (
        "总计 27 个测试用例，全部通过\n"
        "- 认证流程测试: 12/12 passed\n"
        "- 鉴权中间件测试: 9/9 passed\n"
        "- 前端权限控制测试: 6/6 passed\n\n"
        "代码覆盖率: Line 89.2% | Branch 76.5%\n"
        "执行耗时: 34 秒"
    ),
}


TODO2_DEPLOY_REPORT = {
    "service_url": "https://admin.example.com",
    "health_check_result": "All health checks passed — API response time 23ms, DB connection pool healthy",
    "deploy_log": (
        "$ alembic upgrade head\n"
        "[OK] Migration: add_users_and_ownership — 新增 users 表 role 字段\n\n"
        "$ docker build -t data-admin:v1.0.2 .\n"
        "[OK] Image built: data-admin:v1.0.2 (247MB)\n\n"
        "$ kubectl set image deployment/data-admin app=data-admin:v1.0.2\n"
        "[OK] Rolling update: 3/3 pods ready\n\n"
        "$ npm run build && aws s3 sync dist/ s3://admin-frontend/\n"
        "[OK] Frontend deployed, CDN invalidation completed\n\n"
        "$ curl -s https://admin.example.com/api/health | jq .\n"
        '{"status": "ok", "db": "connected", "uptime": "2m31s"}\n\n'
        "冒烟测试: 登录 ✓ | 权限拦截 ✓ | token刷新 ✓ | 用户管理 ✓"
    ),
    "rollback_plan": (
        "1. 数据库: alembic downgrade -1 (users表role字段有默认值，回滚不影响现有数据)\n"
        "2. 后端: kubectl rollout undo deployment/data-admin\n"
        "3. 前端: aws s3 sync s3://admin-frontend-backup/ s3://admin-frontend/\n\n"
        "已通知运营团队分配初始角色，管理员账号已创建并交接。"
    ),
}


TODO2_EXPERIENCE_CARD = {
    "problem": "RBAC权限体系实现中遇到两个关键问题：1) 初期过度设计了完整三级RBAC模型；2) JWT并发刷新导致竞态条件，用户被意外踢到登录页",
    "solution": "权限模型：砍掉动态权限表，固定三种角色+硬编码ROLE_PERMISSIONS常量，代码量减少70%。并发刷新：axios拦截器实现Promise锁，第一个401触发refresh，后续请求排队等待新token后自动重试。",
    "decisions": [
        {
            "point": "权限映射方式",
            "chosen": "硬编码常量而非数据库表",
            "reason": "三种角色变更频率极低（半年一次），动态配置引入不必要的复杂度",
        },
        {
            "point": "并发refresh处理",
            "chosen": "Promise锁",
            "reason": "前端单线程环境Promise足够，mutex反而增加复杂度",
        },
        {
            "point": "Token存储",
            "chosen": "内存变量而非localStorage",
            "reason": "避免跨tab竞争，每个tab独立刷新",
        },
    ],
    "pitfalls": [
        {
            "issue": "过度设计权限模型",
            "cause": "受企业级RBAC最佳实践影响，按照角色-权限-资源三级模型设计",
            "fix": "评估实际需求：内部系统三种角色够用，90%场景不需要动态权限",
        },
        {
            "issue": "refresh锁未在finally中释放",
            "cause": "refresh失败时Promise一直pending，所有后续请求永久阻塞",
            "fix": "在finally块中释放锁，refresh失败直接跳转登录页",
        },
    ],
    "applicable_scenarios": "内部管理系统、角色数量<10的B端产品。不适用于SaaS多租户场景。JWT并发刷新方案适用于任何SPA应用。",
    "tags": ["RBAC", "权限控制", "JWT", "并发处理"],
}


TODO6_TECH_ARCHITECTURE = {
    "architecture_overview": (
        "多源文档统一解析、智能切片、向量化存储系统，支撑下游语义检索。\n\n"
        "四层架构：\n"
        "1. 文档解析层 (Parser) — PDF用PyMuPDF，Markdown用mistune解析AST\n"
        "   - 输出统一的 Document 对象：{sections: [{title, content, level}]}\n\n"
        "2. 切片引擎 (Chunker) — 按语义边界切分检索单元\n"
        "   - 层级切片：先按H1/H2拆分，再按句子边界细分\n"
        "   - chunk大小：200-500 token（tiktoken计算），重叠窗口50 token\n"
        "   - 元数据附带：标题链、源文档ID、位置信息\n\n"
        "3. 向量化层 (Embedder) — OpenAI text-embedding-3-small (1536维)\n"
        "   - 批量处理：每批100条，rate limit控制\n"
        "   - 失败重试：指数退避，3次重试\n\n"
        "4. 存储层 (Store) — Milvus向量索引 + PostgreSQL元数据\n"
        "   - IVF_FLAT索引，nlist=128\n"
        "   - 增量策略：content hash对比，变更时delete+re-insert"
    ),
    "data_model": (
        "documents 表:\n"
        "  - id: UUID, source_type: ENUM, file_path: TEXT\n"
        "  - content_hash: VARCHAR(64), chunk_count: INT\n\n"
        "chunks 表:\n"
        "  - id: UUID, document_id: FK, sequence: INT\n"
        "  - content: TEXT, token_count: INT\n"
        "  - title_chain: TEXT, milvus_id: BIGINT"
    ),
    "api_design": (
        "POST /api/documents/upload → 上传文档，触发异步解析\n"
        "GET /api/documents → 文档列表(状态/chunk数)\n"
        "GET /api/documents/:id/chunks → 查看切片详情\n"
        "POST /api/documents/:id/reprocess → 重新处理\n"
        "POST /api/search → 语义检索(query, top_k)\n"
        "DELETE /api/documents/:id → 删除文档及其向量"
    ),
    "tech_decisions": [
        {
            "decision": "Embedding模型选择",
            "chosen": "text-embedding-3-small 而非 3-large",
            "reason": "500篇文档场景下性价比更优，延迟更低，质量差异<3%",
        },
        {
            "decision": "向量索引类型",
            "chosen": "IVF_FLAT 而非 HNSW",
            "reason": "数据量小时IVF更稳定，内存占用更可控",
        },
        {
            "decision": "增量更新策略",
            "chosen": "content hash 对比",
            "reason": "比逐字段比对更高效，O(1)判断文档是否变更",
        },
    ],
    "implementation_plan": (
        "Phase 1: 文档解析 (3天)\n"
        "  - PDFParser + MarkdownParser 实现\n"
        "  - 统一Document输出格式\n\n"
        "Phase 2: 切片引擎 (2天)\n"
        "  - 层级语义切片算法\n"
        "  - tiktoken精确计算token数\n\n"
        "Phase 3: 向量化+存储 (2天)\n"
        "  - OpenAI embedding批量调用\n"
        "  - Milvus集合创建与写入\n\n"
        "Phase 4: 增量更新+检索API (2天)\n"
        "  - content hash增量检测\n"
        "  - 语义检索接口"
    ),
}


TODO6_REQUIREMENT_SPEC = {
    "background": (
        "企业知识分散在Confluence、飞书、本地文件中，客服回答问题依赖记忆和关键词搜索。"
        "需要构建统一的向量化知识库，将文档切片后embedding存入Milvus，支撑下游语义检索。"
    ),
    "user_scenarios": (
        "1. 管理员上传PDF/Markdown文档到系统\n"
        "2. 系统自动解析、切片、向量化并存入Milvus\n"
        "3. 处理完成后显示文档状态（成功/失败/chunk数量）\n"
        "4. 文档更新时自动检测变更并重新处理\n"
        "5. 客服输入问题，系统检索最相关的知识片段"
    ),
    "goals": (
        "- 支持PDF和Markdown格式\n"
        "- 智能切片：200-500 token/chunk，保持语义完整\n"
        "- OpenAI embedding → Milvus存储\n"
        "- 增量更新：变更文档自动重新处理\n"
        "- 500篇全量导入 < 30分钟"
    ),
    "boundaries": (
        "- 本期不支持Word、HTML等格式\n"
        "- 不做OCR（PDF必须是文本型）\n"
        "- 不做多语言分片优化（以中文为主）"
    ),
    "acceptance_criteria": (
        "1. PDF/Markdown解析准确率 > 95%\n"
        "2. 单文档处理耗时 < 30秒\n"
        "3. 语义检索top-5命中率 > 80%（人工评估）\n"
        "4. 增量更新只处理变更文档\n"
        "5. 处理失败有明确错误提示"
    ),
    "risk_assessment": (
        "- OpenAI API调用费用：500篇×平均20 chunk≈10000次embedding，约$0.2\n"
        "- PDF结构复杂时解析质量下降：提供人工校验入口\n"
        "- Milvus单点故障：K8s部署+定期备份"
    ),
}


TODO9_REQUIREMENT_SPEC = {
    "background": (
        "电商App的搜索功能使用MySQL LIKE查询，响应慢（P95 > 2秒）且不支持模糊匹配。"
        "用户搜索「运动鞋」无法匹配到「跑步鞋」「篮球鞋」等相关商品，转化率持续下降。"
        "需要升级为支持分词、同义词和相关性排序的搜索引擎。"
    ),
    "user_scenarios": (
        "1. 用户在首页搜索框输入关键词\n"
        "2. 输入过程中显示搜索建议（联想词）\n"
        "3. 回车后进入搜索结果页，按相关性排序\n"
        "4. 支持筛选：价格区间、品牌、评分\n"
        "5. 搜索无结果时推荐相似商品"
    ),
    "goals": (
        "- 搜索响应时间 P95 < 200ms\n"
        "- 支持中文分词和同义词扩展\n"
        "- 搜索联想延迟 < 100ms\n"
        "- 搜索结果相关性评分（人工评估 > 85%）\n"
        "- 支持按价格、销量、评分等多维度排序"
    ),
    "boundaries": (
        "- 本期不做图片搜索\n"
        "- 不做个性化排序（v2考虑）\n"
        "- 商品库规模：50万SKU\n"
        "- 不做搜索词纠错（先做同义词）"
    ),
    "acceptance_criteria": (
        "1. 搜索「运动鞋」能匹配到跑步鞋、篮球鞋等\n"
        "2. 50万商品全量索引耗时 < 10分钟\n"
        "3. 搜索QPS > 500（单节点）\n"
        "4. 联想词在用户输入第2个字符后出现\n"
        "5. 筛选条件变化时 < 100ms 刷新结果"
    ),
    "risk_assessment": (
        "- ES集群资源占用较大：预估3节点×8GB内存\n"
        "- 数据同步延迟：MySQL→ES同步延迟控制在5秒内\n"
        "- 分词器选择影响召回率：先用IK分词器，后续可切换jieba"
    ),
}


TODO9_UI_DESIGN = {
    "flow_diagram": (
        "graph TD\n"
        "    A[用户点击搜索框] --> B[显示搜索历史]\n"
        "    B --> C[输入关键词]\n"
        "    C --> D[实时联想词]\n"
        "    D --> E{用户操作}\n"
        "    E -->|选择联想词| F[发起搜索]\n"
        "    E -->|回车| F\n"
        "    F --> G[加载搜索结果]\n"
        "    G --> H{有结果?}\n"
        "    H -->|是| I[展示商品列表]\n"
        "    H -->|否| J[推荐相似商品]\n"
        "    I --> K[筛选/排序]\n"
        "    K --> L[刷新结果]\n"
        "    I --> M[点击商品卡片]\n"
        "    M --> N[商品详情页]"
    ),
    "wireframes": [
        {
            "page_name": "搜索结果页",
            "description": "展示搜索结果列表，支持筛选和排序",
            "html": (
                '<div class="min-h-screen bg-gray-900">'
                '<div class="sticky top-0 bg-gray-900/95 backdrop-blur px-4 py-3 border-b border-gray-800">'
                '<div class="flex items-center gap-3">'
                '<button class="text-gray-400">←</button>'
                '<div class="flex-1 bg-gray-800 rounded-full px-4 py-2 flex items-center">'
                '<span class="text-sm text-white">运动鞋</span>'
                '<span class="ml-auto text-gray-500 text-xs">×</span>'
                "</div></div>"
                '<div class="flex gap-2 mt-3 overflow-x-auto">'
                '<button class="px-3 py-1 bg-indigo-600 text-white rounded-full text-xs">综合</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">销量</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">价格↑</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">评分</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs flex items-center gap-1">筛选 <span>▾</span></button>'
                "</div></div>"
                '<div class="p-4 grid grid-cols-2 gap-3">'
                '<div class="bg-gray-800 rounded-lg overflow-hidden">'
                '<div class="aspect-square bg-gray-700 flex items-center justify-center text-gray-500 text-xs">商品图</div>'
                '<div class="p-3"><p class="text-xs text-white line-clamp-2">Nike Air Max 270 气垫跑步鞋 男款</p>'
                '<p class="mt-1 text-sm font-bold text-red-400">¥699</p>'
                '<p class="text-[10px] text-gray-500">月销 2.3万</p></div></div>'
                '<div class="bg-gray-800 rounded-lg overflow-hidden">'
                '<div class="aspect-square bg-gray-700 flex items-center justify-center text-gray-500 text-xs">商品图</div>'
                '<div class="p-3"><p class="text-xs text-white line-clamp-2">Adidas Ultraboost 轻量跑鞋 女款</p>'
                '<p class="mt-1 text-sm font-bold text-red-400">¥899</p>'
                '<p class="text-[10px] text-gray-500">月销 1.8万</p></div></div>'
                "</div></div>"
            ),
        },
    ],
    "component_specs": [
        {
            "name": "SearchInput",
            "purpose": "搜索输入框+联想词",
            "behavior": "输入防抖300ms触发联想，回车发起搜索",
            "states": "empty / typing / suggesting",
        },
        {
            "name": "ProductGrid",
            "purpose": "商品卡片网格",
            "behavior": "瀑布流加载，支持2列/1列切换",
            "states": "loading / loaded / empty / error",
        },
        {
            "name": "FilterSheet",
            "purpose": "底部弹出筛选面板",
            "behavior": "多维度筛选，确认后刷新结果",
            "states": "collapsed / expanded",
        },
        {
            "name": "SortTabs",
            "purpose": "排序选项卡",
            "behavior": "切换排序方式，价格支持升降序切换",
            "states": "default / active",
        },
    ],
    "interaction_rules": (
        "1. 搜索输入防抖300ms后触发联想词请求\n"
        "2. 联想词列表最多显示8条\n"
        "3. 下拉加载更多商品，每页20条\n"
        "4. 筛选条件变化时列表回到顶部\n"
        "5. 搜索无结果时展示「换个关键词试试」+推荐商品"
    ),
    "responsive_notes": "移动端优先设计，适配 375px-428px 宽度。商品卡片2列网格，间距12px。",
}


TODO9_TECH_ARCHITECTURE = {
    "architecture_overview": (
        "基于 Elasticsearch 的全文搜索系统，替换原有 MySQL LIKE 查询。\n\n"
        "核心模块：\n"
        "1. 搜索服务 (Search Service)\n"
        "   - ES查询构建器：支持分词、同义词扩展、多字段加权\n"
        "   - 聚合查询：筛选面板的品牌/价格区间等聚合数据\n"
        "   - 联想词：基于 completion suggester\n\n"
        "2. 数据同步层 (Sync Layer)\n"
        "   - MySQL → ES 实时同步（基于 binlog/Canal）\n"
        "   - 全量重建索引脚本\n"
        "   - 同步状态监控\n\n"
        "3. 索引管理 (Index Management)\n"
        "   - mapping 定义：中文分词(IK) + 拼音分词\n"
        "   - 同义词词典管理\n"
        "   - 索引别名切换（零停机重建）"
    ),
    "data_model": (
        "ES Index: products\n"
        "  - id: keyword\n"
        "  - title: text (ik_max_word + pinyin)\n"
        "  - brand: keyword + text\n"
        "  - category_path: keyword[]\n"
        "  - price: scaled_float\n"
        "  - sales_count: integer\n"
        "  - rating: float\n"
        "  - tags: keyword[]\n"
        "  - suggest: completion (联想词)\n"
        "  - updated_at: date\n\n"
        "MySQL (source of truth):\n"
        "  products, categories, brands 表不变\n"
        "  新增 sync_status 表跟踪同步进度"
    ),
    "api_design": (
        "GET /api/search?q=运动鞋&page=1&size=20 → 搜索结果+聚合\n"
        "GET /api/search/suggest?q=运动 → 联想词列表(max 8)\n"
        "POST /api/search/reindex → 触发全量重建 [admin]\n"
        "GET /api/search/stats → 索引状态和同步延迟 [admin]"
    ),
    "tech_decisions": [
        {
            "decision": "搜索引擎选择",
            "chosen": "Elasticsearch 8.x",
            "reason": "中文分词生态成熟(IK)，聚合查询能力强，运维工具链完善",
        },
        {
            "decision": "数据同步方案",
            "chosen": "Canal监听binlog",
            "reason": "实时性好(<5s延迟)，对业务代码零侵入",
        },
        {
            "decision": "分词器选择",
            "chosen": "IK分词器 + 自定义同义词",
            "reason": "中文分词效果好，支持热更新词典，不需要重建索引",
        },
    ],
    "implementation_plan": (
        "Phase 1: ES基础搭建 (2天)\n"
        "  - ES集群部署(3节点) + IK插件\n"
        "  - products索引mapping设计\n"
        "  - 全量索引脚本\n\n"
        "Phase 2: 搜索API (2天)\n"
        "  - 多字段加权搜索\n"
        "  - 筛选和排序\n"
        "  - 联想词(completion suggester)\n\n"
        "Phase 3: 实时同步 (2天)\n"
        "  - Canal部署和配置\n"
        "  - 增量同步服务\n"
        "  - 同步监控告警"
    ),
}


TODO9_DEV_REPORT = {
    "execution_log": (
        "$ docker-compose up -d elasticsearch kibana\n"
        "[OK] ES cluster health: green (3 nodes)\n\n"
        "$ python scripts/create_index.py\n"
        "[OK] Index 'products_v1' created with IK analyzer\n"
        "[OK] Alias 'products' → 'products_v1'\n\n"
        "$ python scripts/full_reindex.py\n"
        "Indexing: 100%|████████████| 500000/500000 [08:32<00:00, 976.5 docs/s]\n"
        "[OK] 500,000 products indexed in 8m32s\n\n"
        "$ pytest tests/search/ -v\n"
        "tests/search/test_query.py::test_basic_search PASSED\n"
        "tests/search/test_query.py::test_synonym_match PASSED\n"
        "tests/search/test_query.py::test_filter_price_range PASSED\n"
        "tests/search/test_query.py::test_suggest PASSED\n"
        "tests/search/test_sync.py::test_incremental_sync PASSED\n"
        "...\n"
        "18 passed in 12.41s\n\n"
        "$ ab -n 1000 -c 50 'http://localhost:8000/api/search?q=运动鞋'\n"
        "Requests per second: 682.31 [#/sec]\n"
        "Time per request: 73.3ms [mean]\n"
        "95% <= 142ms"
    ),
    "code_changes": [
        "backend/src/search/service.py — ES查询构建器，支持多字段加权+同义词",
        "backend/src/search/sync.py — Canal binlog消费者，实时同步到ES",
        "backend/src/search/index.py — 索引管理：mapping定义+别名切换",
        "backend/scripts/full_reindex.py — 全量重建脚本(批量bulk)",
        "backend/src/api/routes/search.py — 搜索+联想词+管理接口",
        "config/elasticsearch/synonyms.txt — 同义词词典",
        "config/canal/instance.properties — Canal配置",
    ],
    "test_results": "18/18 tests passed | 搜索QPS: 682 (目标500) | P95延迟: 142ms (目标200ms) | 同义词覆盖: 92%",
    "decisions_made": [
        {
            "decision": "批量索引使用bulk API而非单条写入",
            "reason": "50万商品单条写入需要2小时，bulk批量(每批5000)只需8分钟",
        },
        {
            "decision": "搜索结果缓存在应用层做而非ES层",
            "reason": "热门搜索词QPS高，Redis缓存60秒减少ES压力",
        },
    ],
}



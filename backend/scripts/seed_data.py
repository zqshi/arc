"""Full-chain seed data for Arc demo: project → version → todo → pipeline → conversation → messages → artifacts → agent sessions → experiences.

Called from main.py on first startup for each seed user. All data is inserted via raw SQL
to avoid domain validation (seed data includes mid-pipeline states).
Uses random UUIDs so the function can be called for multiple users without conflicts.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ═══════════════════════════════════════════════════════════════════
# Todo1: 实现批量数据导出功能 (active, at ui_design)
# ═══════════════════════════════════════════════════════════════════

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
                '</div></div>'
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
                '</div></div>'
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
                '</tbody></table></div>'
                '<p class="mt-2 text-xs text-gray-600">显示前 2 条 / 共 87,432 条</p></div>'
                '<div class="flex items-center justify-between">'
                '<p class="text-xs text-gray-500">预计文件大小: ~12.3 MB  |  预计耗时: ~2 分钟</p>'
                '<button class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-medium">确认导出</button>'
                '</div></div></div>'
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
                '</tbody></table></div></div></div>'
            ),
        },
    ],
    "component_specs": [
        {"name": "DataTypeSelector", "purpose": "数据类型切换", "behavior": "点击切换，高亮选中项", "states": "default / selected / disabled"},
        {"name": "FilterPanel", "purpose": "筛选条件面板", "behavior": "修改条件后刷新预览", "states": "default / loading / error"},
        {"name": "DataPreview", "purpose": "数据预览表格", "behavior": "显示前20条和总数", "states": "empty / loading / loaded / over-limit"},
        {"name": "ExportButton", "purpose": "触发异步导出", "behavior": "确认后提交任务", "states": "default / loading / disabled"},
        {"name": "ExportHistoryTable", "purpose": "历史导出记录", "behavior": "按时间倒序，支持下载/重试", "states": "empty / loaded"},
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

TODO1_CLAR_MESSAGES = [
    ("assistant", "你好！我来帮你梳理「实现批量数据导出功能」的需求。\n\n先从问题本身开始——批量数据导出，这个需求主要想解决什么问题？目前用户遇到了哪些痛点？"),
    ("user", "运营团队每个月都要导出用户行为数据做分析报告，现在只能让开发人员直连数据库手动查出来，效率很低，而且直连数据库有安全风险。需要一个自助的导出功能。"),
    ("assistant", "明白了。核心问题是运营团队对数据的自助获取能力缺失，当前依赖开发资源且有安全隐患。\n\n追问几个细节：\n1. 需要导出的数据类型有哪些？只有用户行为，还是也包括订单、商品等？\n2. 数据量级大概多少？日均多少行？"),
    ("user", "数据类型主要三种：用户行为数据、订单数据、商品数据。用户行为是最大的，日均大概3-5万行，一个月下来差不多100万行。不过一般运营导出时会按条件筛选，实际导出量在10万行左右。"),
    ("assistant", "好的，信息很清晰。10万行级别的导出对性能有一定要求。\n\n现在推进到使用场景——描述一下运营人员的典型操作流程？他们从哪里进入，需要设置哪些筛选条件？"),
    ("user", "登录后台管理系统，进入数据导出页面，选择数据类型，然后设置日期范围和筛选条件比如用户类型、地区什么的，最好能先预览一下数据对不对，确认后再导出。导出应该是后台执行的，完成后通知我下载就行。"),
    ("assistant", "很好的场景描述。异步导出+通知的模式非常合理。\n\n关于边界和约束：\n1. 导出格式？CSV还是也要支持Excel？\n2. 单次导出有上限吗？\n3. 有没有时间节点的要求？"),
    ("user", "先只支持CSV就够了，Excel后面再考虑。单次上限50万行吧，再大了没有实际意义。下个月初要用，差不多两周内完成。"),
]

TODO1_UI_MESSAGES = [
    ("assistant", "需求已经明确，现在来设计交互方案。\n\n我会产出 Mermaid 流程图和 HTML 线框图，让你能直观看到设计方案。「批量数据导出」的核心操作路径是什么？"),
    ("user", "从后台侧边栏「数据管理」分类下进入「数据导出」页面。核心路径就是：选类型 → 设条件 → 预览 → 导出 → 等通知 → 下载。另外需要一个导出历史页面查看之前的导出记录。"),
    ("assistant", "好的，核心路径很清晰。我设计了两个页面：\n\n**页面1 - 数据导出配置页**\n- 顶部：数据类型切换（tab形式）\n- 中间：筛选条件面板（2列网格布局）\n- 下方：数据预览表格（前20条+总数）\n- 底部：导出按钮和预估信息\n\n**页面2 - 导出历史页**\n- 表格列出所有导出记录\n- 包含状态（排队中/导出中/完成/失败）\n- 完成的可下载，失败的可重试\n\n流程图和线框图已生成，请查看产物区域。"),
    ("user", "可以，就按这个来。注意预览数据量太大时要给提示，超过50万行直接禁止导出。"),
]


# ═══════════════════════════════════════════════════════════════════
# Todo2: 用户权限与角色管理 (done, all phases completed)
# ═══════════════════════════════════════════════════════════════════

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
                '</div>'
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
                '</tbody></table></div></div></div>'
            ),
        },
    ],
    "component_specs": [
        {"name": "UserTable", "purpose": "用户列表", "behavior": "展示用户信息，支持角色编辑和状态切换", "states": "empty / loaded / loading"},
        {"name": "RoleBadge", "purpose": "角色标签", "behavior": "根据角色显示不同颜色", "states": "admin(red) / operator(blue) / readonly(gray)"},
        {"name": "AddUserModal", "purpose": "新增用户弹窗", "behavior": "输入用户名+密码+角色，提交创建", "states": "default / validating / error"},
        {"name": "PermissionGuard", "purpose": "权限守卫组件", "behavior": "根据当前用户角色决定子元素是否渲染", "states": "visible / hidden"},
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
        {"decision": "角色-权限映射方式", "chosen": "硬编码常量", "reason": "三种固定角色，不需要动态配置的灵活性，代码量减少70%"},
        {"decision": "会话管理方案", "chosen": "JWT 而非 Session", "reason": "前后端分离架构，无需服务端存储会话状态"},
        {"decision": "Token 过期策略", "chosen": "access_token 30min + refresh_token 7d", "reason": "平衡安全性和用户体验，短token减少泄露窗口"},
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
        {"decision": "使用 Promise 锁处理并发 refresh", "reason": "避免多个401请求同时触发refresh导致竞态条件"},
        {"decision": "权限映射硬编码在常量中", "reason": "三种固定角色变更频率极低，数据库方案引入不必要的复杂度"},
        {"decision": "前端 axios 拦截器统一处理 401", "reason": "避免每个API调用都手动处理token过期逻辑"},
    ],
}

TODO2_TEST_REPORT = {
    "criteria_verification": [
        {"criteria": "管理员可执行所有操作，包括用户管理", "status": "pass", "evidence": "admin角色通过所有接口测试（12/12），包括用户CRUD和角色变更"},
        {"criteria": "运营可导出数据、查看看板，不可修改系统配置", "status": "pass", "evidence": "operator角色导出和看板接口返回200，用户管理和配置接口返回403"},
        {"criteria": "只读用户仅可查看看板", "status": "pass", "evidence": "readonly角色仅看板接口200，导出和配置接口均返回403"},
        {"criteria": "越权API调用返回403", "status": "pass", "evidence": "所有越权场景均返回403 Forbidden，响应体包含具体权限缺失信息"},
        {"criteria": "access_token 30分钟过期，refresh_token 7天", "status": "pass", "evidence": "token过期后返回401，refresh成功续期，过期refresh返回401并跳转登录"},
    ],
    "issues_found": [
        {"description": "并发refresh请求偶发竞态", "severity": "medium", "suggestion": "已通过Promise锁修复，建议增加并发场景的E2E测试覆盖"},
        {"description": "角色变更后旧token仍有效", "severity": "low", "suggestion": "设计决策：接受最多30分钟延迟，无需修复"},
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
        {"point": "权限映射方式", "chosen": "硬编码常量而非数据库表", "reason": "三种角色变更频率极低（半年一次），动态配置引入不必要的复杂度"},
        {"point": "并发refresh处理", "chosen": "Promise锁", "reason": "前端单线程环境Promise足够，mutex反而增加复杂度"},
        {"point": "Token存储", "chosen": "内存变量而非localStorage", "reason": "避免跨tab竞争，每个tab独立刷新"},
    ],
    "pitfalls": [
        {"issue": "过度设计权限模型", "cause": "受企业级RBAC最佳实践影响，按照角色-权限-资源三级模型设计", "fix": "评估实际需求：内部系统三种角色够用，90%场景不需要动态权限"},
        {"issue": "refresh锁未在finally中释放", "cause": "refresh失败时Promise一直pending，所有后续请求永久阻塞", "fix": "在finally块中释放锁，refresh失败直接跳转登录页"},
    ],
    "applicable_scenarios": "内部管理系统、角色数量<10的B端产品。不适用于SaaS多租户场景。JWT并发刷新方案适用于任何SPA应用。",
    "tags": ["RBAC", "权限控制", "JWT", "并发处理"],
}

TODO2_CLAR_MESSAGES = [
    ("assistant", "你好！我来帮你梳理「用户权限与角色管理」的需求。\n\n先聊聊基本诉求——为什么需要权限管理？现在是什么状态？"),
    ("user", "现在后台没有权限控制，所有人都能看到所有数据、执行所有操作。运营同事误删过一次导出配置，而且数据安全审计也要求必须做权限隔离。"),
    ("assistant", "明确了。两个驱动力：操作安全（防误操作）和合规审计。\n\n需要哪些角色？各角色的核心权限差异是什么？"),
    ("user", "三种角色就够了：管理员可以做所有事情，运营人员可以导出数据和看看板但不能改配置，只读用户只能看看板。"),
    ("assistant", "清晰。确认几个细节：\n1. 角色可以自定义吗，还是固定这三种？\n2. 一个用户可以有多个角色吗？\n3. 需要数据级别的权限隔离吗？比如运营A只能看华东数据？"),
    ("user", "先固定三种角色，不做自定义。一个用户一个角色就行。数据隔离先不做，后面再考虑。"),
    ("assistant", "好的，需求边界清晰：\n- 固定三角色：管理员 / 运营 / 只读\n- 单角色绑定，无数据级隔离\n- 关键控制点：导出操作、配置修改、看板查看\n\n验收标准：\n1. 管理员可执行所有操作\n2. 运营可导出+看板，不可改配置\n3. 只读仅可看板\n4. 越权操作返回403\n5. token过期30分钟，refresh 7天\n\n需求确认完成。"),
    ("user", "确认，就这些。"),
]

TODO2_UI_MESSAGES = [
    ("assistant", "开始设计权限管理的交互方案。核心页面有哪些？"),
    ("user", "需要一个用户管理页面，管理员能在上面给用户分配角色。另外各页面要根据角色隐藏没权限的操作按钮。"),
    ("assistant", "方案如下：\n\n**用户管理页**（仅管理员可见）\n- 用户列表：显示用户名、角色、状态\n- 操作列：修改角色、禁用账号\n- 新增用户弹窗：用户名+初始密码+角色选择\n\n**全局权限控制**\n- 侧边栏：根据角色隐藏「系统配置」入口\n- 导出按钮：只读用户不可见\n- 配置项：运营和只读用户不可编辑\n\n线框图和组件规格已生成。"),
    ("user", "可以，简洁够用。"),
]

TODO2_ARCH_MESSAGES = [
    ("assistant", "进入技术架构设计。RBAC实现方案，你倾向于哪种？\n1. 前端路由守卫 + 后端中间件双重控制\n2. 纯后端控制，前端只做展示层适配"),
    ("user", "双重控制更安全，前后端都做。后端是权威，前端是体验优化。"),
    ("assistant", "同意。架构方案：\n\n**鉴权层**\n- JWT token 中携带 role claim\n- 后端 FastAPI dependency 解析 token 并注入 current_user\n- 基于装饰器的权限检查：`@require_role(\"admin\")`\n\n**数据模型**\n- users 表增加 role 字段（admin/operator/readonly）\n- 不单独建 permissions 表，角色-权限映射硬编码在常量中\n\n**前端适配**\n- AuthContext 存储用户信息和角色\n- ProtectedRoute 组件做路由级守卫\n- usePermission hook 做按钮级控制\n\n技术风险：JWT 过期时间和 refresh 机制需要处理好，避免用户操作中途被踢。"),
    ("user", "没问题，就这个方案。JWT过期设30分钟，refresh token 7天。"),
]

TODO2_EXTRACT_MESSAGES = [
    ("assistant", "权限体系已上线运行稳定。来沉淀一下这次的经验。\n\n这次做权限管理，你觉得最值得记录的点是什么？"),
    ("user", "两个：一是RBAC不要过度设计，三种固定角色比动态权限表简单太多了，维护成本极低；二是JWT的refresh机制，一开始没做好导致用户频繁被踢出，后来加了静默刷新才解决。"),
    ("assistant", "好的。我提炼了两张经验卡片：\n\n**经验1: RBAC权限模型设计的最小权限原则**\n- 问题：初期想做完整的RBAC三级模型\n- 方案：固定角色+硬编码权限映射，代码量减少70%\n- 适用场景：角色数量<10的内部系统\n\n**经验2: JWT静默刷新的并发处理**\n- 问题：access_token过期后多并发请求同时收到401\n- 方案：axios拦截器+Promise锁，保证只发一次refresh\n- 陷阱：并发请求时多个refresh同时发出导致竞态\n\n确认后归档。"),
    ("user", "准确，确认。"),
]


# ═══════════════════════════════════════════════════════════════════
# Todo6: 文档解析与向量化 (active, at architecture)
# ═══════════════════════════════════════════════════════════════════

TODO6_CLAR_MESSAGES = [
    ("assistant", "你好！我来帮你梳理「文档解析与向量化」的需求。\n\n先说说背景——你们现在的知识库是怎么管理的？文档存在哪里？"),
    ("user", "目前文档散落在各处——Confluence、飞书文档、本地的Word和PDF。客服回答问题全靠记忆和搜索，效率很低。想做一个统一的向量化知识库，支持语义检索。"),
    ("assistant", "明白了。核心诉求是：将多源异构文档统一解析、切片、embedding后存入向量库，支撑下游的语义检索。\n\n几个关键问题：\n1. 文档格式优先支持哪些？\n2. 预估文档量多大？\n3. 更新频率？"),
    ("user", "先支持PDF和Markdown就行。文档大概500篇左右，每周新增10-20篇。需要支持增量更新。"),
    ("assistant", "需求边界清晰了。验收标准：\n1. 支持PDF和Markdown格式\n2. 智能切片，单个chunk 200-500 token\n3. OpenAI embedding接入Milvus\n4. 支持增量更新\n5. 500篇全量导入 < 30分钟\n\n需求澄清完成，进入架构设计。"),
]

TODO6_ARCH_MESSAGES = [
    ("assistant", "进入架构设计。核心模块：\n1. **文档解析层**：PDF用PyMuPDF，Markdown直接解析AST\n2. **切片策略**：按标题层级递归分段，保持语义完整性\n3. **向量化层**：OpenAI text-embedding-3-small\n4. **存储层**：Milvus + PostgreSQL 元数据\n\n你们有GPU资源吗？考虑是否自建embedding服务。"),
    ("user", "没有GPU，用OpenAI API就行。K8s集群上已有Milvus测试实例。主要关心切片质量和增量更新方案。"),
    ("assistant", "切片策略详细设计：\n\n**层级切片算法**\n- 第一层：按 H1/H2 标题拆分大段\n- 第二层：对超过500 token的段落，按句子边界继续拆分\n- 保持上下文：每个chunk附带「标题链」元数据，如「安装指南 > 环境配置 > Python依赖」\n\n**增量更新方案**\n- 文档指纹（content hash）判断是否变更\n- 变更时删除旧chunks，重新切片入库\n- 新增文档直接追加\n\n**技术选型**\n- PyMuPDF: PDF解析，保持段落结构\n- mistune: Markdown AST解析\n- tiktoken: 精确计算token数\n- Milvus: 向量存储与检索，IVF_FLAT索引\n\n正在整理架构方案文档..."),
]

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
        {"decision": "Embedding模型选择", "chosen": "text-embedding-3-small 而非 3-large", "reason": "500篇文档场景下性价比更优，延迟更低，质量差异<3%"},
        {"decision": "向量索引类型", "chosen": "IVF_FLAT 而非 HNSW", "reason": "数据量小时IVF更稳定，内存占用更可控"},
        {"decision": "增量更新策略", "chosen": "content hash 对比", "reason": "比逐字段比对更高效，O(1)判断文档是否变更"},
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


# ═══════════════════════════════════════════════════════════════════
# Project 3: 移动电商App — Todo9: 商品搜索优化 (active, at development)
# ═══════════════════════════════════════════════════════════════════

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
                '</div></div>'
                '<div class="flex gap-2 mt-3 overflow-x-auto">'
                '<button class="px-3 py-1 bg-indigo-600 text-white rounded-full text-xs">综合</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">销量</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">价格↑</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs">评分</button>'
                '<button class="px-3 py-1 bg-gray-800 text-gray-300 rounded-full text-xs flex items-center gap-1">筛选 <span>▾</span></button>'
                '</div></div>'
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
                '</div></div>'
            ),
        },
    ],
    "component_specs": [
        {"name": "SearchInput", "purpose": "搜索输入框+联想词", "behavior": "输入防抖300ms触发联想，回车发起搜索", "states": "empty / typing / suggesting"},
        {"name": "ProductGrid", "purpose": "商品卡片网格", "behavior": "瀑布流加载，支持2列/1列切换", "states": "loading / loaded / empty / error"},
        {"name": "FilterSheet", "purpose": "底部弹出筛选面板", "behavior": "多维度筛选，确认后刷新结果", "states": "collapsed / expanded"},
        {"name": "SortTabs", "purpose": "排序选项卡", "behavior": "切换排序方式，价格支持升降序切换", "states": "default / active"},
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
        {"decision": "搜索引擎选择", "chosen": "Elasticsearch 8.x", "reason": "中文分词生态成熟(IK)，聚合查询能力强，运维工具链完善"},
        {"decision": "数据同步方案", "chosen": "Canal监听binlog", "reason": "实时性好(<5s延迟)，对业务代码零侵入"},
        {"decision": "分词器选择", "chosen": "IK分词器 + 自定义同义词", "reason": "中文分词效果好，支持热更新词典，不需要重建索引"},
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
        {"decision": "批量索引使用bulk API而非单条写入", "reason": "50万商品单条写入需要2小时，bulk批量(每批5000)只需8分钟"},
        {"decision": "搜索结果缓存在应用层做而非ES层", "reason": "热门搜索词QPS高，Redis缓存60秒减少ES压力"},
    ],
}

TODO9_CLAR_MESSAGES = [
    ("assistant", "你好！来梳理「商品搜索优化」需求。\n\n先描述一下当前搜索的问题？用户反馈集中在哪些方面？"),
    ("user", "现在搜索太慢了，2秒才出结果。而且搜「运动鞋」只能精确匹配，搜不到跑步鞋、篮球鞋这些。用户反馈找不到想要的商品，搜索转化率一直在降。"),
    ("assistant", "核心问题：性能差 + 召回率低。\n\n几个细节：\n1. 商品库多大？\n2. 搜索量（QPS）？\n3. 现在用什么方案？MySQL LIKE？"),
    ("user", "50万SKU，日搜索量大概100万次，高峰QPS在500左右。现在就是MySQL全表LIKE，没有任何分词和索引优化。"),
    ("assistant", "50万SKU + 500 QPS，MySQL LIKE完全扛不住。需要专业搜索引擎。\n\n需求边界确认：\n1. 搜索联想词要不要做？\n2. 需要哪些筛选维度？\n3. 有没有个性化排序的需求（千人千面）？"),
    ("user", "联想词一定要做，体验很重要。筛选需要价格、品牌、评分。个性化排序先不做，下个版本再考虑。"),
]

TODO9_UI_MESSAGES = [
    ("assistant", "进入交互设计。移动端搜索的核心体验点：\n1. 搜索输入 → 联想词\n2. 搜索结果 → 商品卡片列表\n3. 筛选排序 → 底部弹出面板\n\n首先确认搜索结果页的布局：2列网格还是1列大卡？"),
    ("user", "2列网格，跟主流电商一样。卡片要有商品图、标题、价格、销量。排序tab放在搜索框下面固定位置。"),
    ("assistant", "方案已生成：\n\n**搜索结果页**\n- 顶部固定搜索框+排序tabs\n- 2列商品网格瀑布流\n- 底部弹出筛选面板\n- 无结果时推荐相似商品\n\n流程图和线框图请查看产物区域。"),
    ("user", "OK，就这样。"),
]

TODO9_ARCH_MESSAGES = [
    ("assistant", "架构设计核心决策：搜索引擎选型。\n\n选项：\n1. Elasticsearch — 成熟稳定，中文生态好(IK分词器)\n2. Meilisearch — 轻量开箱即用，但中文支持弱\n3. 自建倒排索引 — 灵活但工作量大\n\n你们有ES运维经验吗？"),
    ("user", "运维有ES经验，选ES吧。主要关心数据从MySQL同步到ES的方案，要求延迟低。"),
    ("assistant", "ES确定。数据同步方案：\n\n**方案A: Canal监听binlog**\n- 优点：实时性好(<5s)，对业务零侵入\n- 缺点：需要部署Canal实例\n\n**方案B: 双写**\n- 优点：简单直接\n- 缺点：侵入业务代码，事务一致性难保证\n\n推荐方案A。"),
    ("user", "方案A，运维那边有Canal经验。延迟5秒内完全可以接受。"),
]


# ═══════════════════════════════════════════════════════════════════
# Project 4: 内部OKR管理平台 — Todo11: OKR目标树管理 (active, at clarification)
# ═══════════════════════════════════════════════════════════════════

TODO11_CLAR_MESSAGES = [
    ("assistant", "你好！来梳理「OKR目标树管理」的需求。\n\n先聊聊背景——你们现在怎么管理OKR的？遇到什么问题？"),
    ("user", "现在用飞书文档写OKR，每个季度手动创建文档，对齐上级目标全靠口头沟通。问题是：看不到全局目标树、无法追踪进度、对齐关系模糊。"),
    ("assistant", "明白。核心痛点：\n1. 无法可视化全局目标树\n2. 进度追踪靠手动更新\n3. 上下级目标对齐关系不清晰\n\n几个问题：\n1. 团队规模多大？\n2. OKR周期？季度？\n3. 需要和哪些系统打通？"),
    ("user", "100人左右，按季度做OKR。暂时不用和其他系统打通，先解决看得见、管得住的问题。目标树要能展开收起，每个KR要有进度条。"),
]


# ═══════════════════════════════════════════════════════════════════
# Experiences
# ═══════════════════════════════════════════════════════════════════

EXPERIENCES_DATA = [
    {
        "title": "大数据量CSV导出的流式写入方案",
        "scope": "project",
        "status": "confirmed",
        "problem": "一次性将10万行数据加载到内存生成CSV会导致OOM，测试环境8GB内存的容器直接被OOM Killer干掉",
        "solution": "采用分批查询+流式写入：每次从数据库查询5000行，逐批写入CSV文件，内存占用恒定在~50MB以内。使用Python原生csv模块的writer，配合文件流逐行写入。",
        "decisions": ["选择分批大小5000行：太小影响查询效率（频繁IO），太大占用内存", "使用原生csv模块而非pandas：避免引入重量级依赖，且pandas的to_csv会一次性加载所有数据"],
        "pitfalls": ["CSV注入风险：以=、+、-、@开头的单元格内容需要加单引号转义，否则Excel会当公式执行", "编码问题：需要显式写入UTF-8 BOM头(\\xef\\xbb\\xbf)，否则Excel打开中文乱码。Python默认UTF-8不带BOM"],
        "applicable_scenarios": "涉及大数据量文件生成的后台导出功能，特别是内存受限的容器环境",
        "tags": [{"label": "性能优化", "color": "#10B981"}, {"label": "数据导出", "color": "#6366F1"}],
        "confidence": 0.85,
        "reuse_count": 3,
        "source_todo": "todo1",
    },
    {
        "title": "异步任务队列的并发控制设计",
        "scope": "project",
        "status": "confirmed",
        "problem": "多个用户同时触发导出任务会耗尽数据库连接和CPU资源，导致所有任务都变慢甚至超时",
        "solution": "使用内存任务队列+信号量控制并发数为3。超出的任务排队等待，前端通过WebSocket实时推送任务状态变化（排队中→执行中→完成/失败）。",
        "decisions": ["选择内存队列而非Redis：单机部署场景不需要分布式，减少外部依赖", "并发数设为3：基于服务器4核CPU、数据库连接池20的经验值，3个任务约占用60%资源"],
        "pitfalls": ["内存队列在服务重启时丢失：需要将任务元数据持久化到数据库，重启后扫描pending状态恢复", "WebSocket断连后用户收不到通知：需要在前端做轮询兜底（每30秒查一次状态）"],
        "applicable_scenarios": "后台异步任务处理，涉及资源限制的场景。特别是IO密集型任务的排队机制。",
        "tags": [{"label": "架构设计", "color": "#F59E0B"}, {"label": "并发控制", "color": "#EF4444"}],
        "confidence": 0.78,
        "reuse_count": 1,
        "source_todo": "todo1",
    },
    {
        "title": "RBAC权限模型设计的最小够用原则",
        "scope": "project",
        "status": "confirmed",
        "problem": "初期方案设计了完整的RBAC三级模型（角色-权限-资源），包含动态权限表、权限继承、权限组等。评估发现工期翻倍且维护复杂。",
        "solution": "砍掉动态权限表，固定三种角色（admin/operator/readonly），权限映射硬编码在ROLE_PERMISSIONS常量中。代码量从预估的1200行减少到350行，且零运行时查询开销。",
        "decisions": ["硬编码权限映射：三种角色的权限变更频率极低（半年可能改一次），不值得做数据库配置化", "不做数据级隔离：当前运营团队只有5人，数据隔离需求不强烈，后续按需加"],
        "pitfalls": ["容易过度设计：内部工具的权限需求远比想象的简单，90%的场景三种角色就够了", "角色变更需要重新部署：可接受的代价，因为变更频率极低"],
        "applicable_scenarios": "内部管理系统、角色数量<10的B端产品。不适用于SaaS多租户场景。",
        "tags": [{"label": "架构设计", "color": "#F59E0B"}, {"label": "权限控制", "color": "#EF4444"}],
        "confidence": 0.92,
        "reuse_count": 2,
        "source_todo": "todo2",
    },
    {
        "title": "JWT静默刷新的并发竞态处理",
        "scope": "personal",
        "status": "confirmed",
        "problem": "页面同时发出5个API请求，access_token过期后5个请求同时收到401，各自触发refresh请求。第一个refresh成功后其余4个用旧refresh_token请求导致失败，用户被踢到登录页。",
        "solution": "在axios拦截器中实现Promise锁：第一个401触发refresh并缓存Promise，后续401等待同一个Promise resolve后用新token重试原请求。refresh完成后释放锁。",
        "decisions": ["Promise锁而非mutex：前端单线程环境下Promise足够，mutex反而引入不必要的复杂度", "用变量而非localStorage存锁状态：避免跨tab竞争，每个tab独立刷新"],
        "pitfalls": ["refresh本身也可能失败（网络问题）：需要在finally中释放锁，否则所有后续请求永久阻塞", "refresh_token也过期时应该直接跳转登录，不要无限重试"],
        "applicable_scenarios": "任何使用JWT + refresh_token的前端应用，特别是SPA中存在并发API请求的场景。",
        "tags": [{"label": "前端", "color": "#34D399"}, {"label": "认证", "color": "#EF4444"}],
        "confidence": 0.88,
        "reuse_count": 4,
        "source_todo": "todo2",
    },
    {
        "title": "文档切片粒度对RAG检索质量的影响",
        "scope": "project",
        "status": "draft",
        "problem": "初始方案按固定500 token切片，测试发现检索质量不稳定：有时chunk截断了一个完整概念，返回的内容缺少上下文。",
        "solution": "改为层级语义切片：先按标题(H1/H2)拆分大段，再对超长段按句子边界细分。每个chunk附带「标题链」元数据，检索时同时返回标题链帮助理解上下文。chunk间保留50 token重叠避免信息丢失。",
        "decisions": ["标题优先拆分：文档的标题天然是语义边界", "50 token重叠：经验值，太少丢信息太多浪费空间"],
        "pitfalls": ["表格类内容不适合按句子拆分：需要特殊处理，将整个表格作为独立chunk", "PDF的标题识别依赖字号判断，部分文档字号不规范会导致误判"],
        "applicable_scenarios": "RAG系统的文档预处理环节，特别是中文技术文档的切片场景。",
        "tags": [{"label": "AI", "color": "#A78BFA"}, {"label": "RAG", "color": "#6366F1"}],
        "confidence": 0.65,
        "reuse_count": 0,
        "source_todo": "todo6",
    },
]


# ═══════════════════════════════════════════════════════════════════
# Main seed function
# ═══════════════════════════════════════════════════════════════════

async def create_seed_data(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Insert full demo data for the given user via raw SQL."""

    now = datetime.now(UTC)

    # ── Generate all IDs upfront ────────────────────────────────
    project1_id = uuid.uuid4()
    project2_id = uuid.uuid4()
    ver1_id, ver2_id, ver3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo1_id, todo2_id, todo3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    todo4_id, todo5_id = uuid.uuid4(), uuid.uuid4()
    todo6_id, todo7_id, todo8_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    # Todo1 pipeline phase IDs
    t1_phase = {pt: uuid.uuid4() for pt in ["clarification", "ui_design", "architecture", "development", "testing", "deployment", "extraction"]}
    # Todo2 pipeline phase IDs
    t2_phase = {pt: uuid.uuid4() for pt in ["clarification", "ui_design", "architecture", "development", "testing", "deployment", "extraction"]}
    # Todo6 pipeline phase IDs
    t6_phase = {pt: uuid.uuid4() for pt in ["clarification", "ui_design", "architecture", "development", "testing", "deployment", "extraction"]}

    # Conversation IDs
    t1_conv = {"clarification": uuid.uuid4(), "ui_design": uuid.uuid4()}
    t2_conv = {"clarification": uuid.uuid4(), "ui_design": uuid.uuid4(), "architecture": uuid.uuid4(), "extraction": uuid.uuid4()}
    t6_conv = {"clarification": uuid.uuid4(), "architecture": uuid.uuid4()}

    # Agent session IDs for todo2
    t2_agent = {"development": uuid.uuid4(), "testing": uuid.uuid4(), "deployment": uuid.uuid4()}

    # ── Helper ──────────────────────────────────────────────────

    async def _insert(table: str, values: dict) -> None:
        cols = ", ".join(f'"{k}"' if k == "order" else k for k in values.keys())
        params = ", ".join(f":{k}" for k in values.keys())
        await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({params})"), values)

    async def _insert_messages(conv_id: uuid.UUID, messages: list[tuple[str, str]], base_time: datetime) -> None:
        for i, (role, content) in enumerate(messages):
            await _insert("messages", {
                "id": uuid.uuid4(), "conversation_id": conv_id,
                "role": role, "content": content,
                "created_at": base_time + timedelta(minutes=i * 3),
            })

    # ═══════════════════════════════════════════════════════════
    # Project 1: 数据管理后台
    # ═══════════════════════════════════════════════════════════

    await _insert("projects", {
        "id": project1_id, "user_id": user_id,
        "name": "数据管理后台",
        "description": "企业级数据管理与分析平台，支持多维度数据导出、可视化看板和权限管理",
        "tech_stack": "React + FastAPI + PostgreSQL + Celery",
        "status": "active",
        "created_at": now - timedelta(days=21), "updated_at": now,
    })

    # Version v1.0 (active)
    await _insert("versions", {
        "id": ver1_id, "project_id": project1_id,
        "name": "v1.0", "goal": "核心导出功能 + 权限体系",
        "status": "active", "order": 1,
        "created_at": now - timedelta(days=21), "updated_at": now,
    })

    # Version v1.1 (planning)
    await _insert("versions", {
        "id": ver2_id, "project_id": project1_id,
        "name": "v1.1", "goal": "可视化看板 + 定时导出",
        "status": "planning", "order": 2,
        "created_at": now - timedelta(days=5), "updated_at": now,
    })

    # ── Todo1: 实现批量数据导出功能 (active, at ui_design) ──

    await _insert("todos", {
        "id": todo1_id, "user_id": user_id, "project_id": project1_id, "version_id": ver1_id,
        "title": "实现批量数据导出功能",
        "description": "支持管理员按日期范围导出用户行为/订单/商品数据为CSV，异步执行+通知下载",
        "status": "active", "priority": 1, "current_phase": "ui_design",
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "核心功能", "color": "#6366F1"}]),
        "created_at": now - timedelta(days=10), "updated_at": now,
    })

    # Conversations (must exist before pipeline_phases FK)
    for purpose, conv_id in t1_conv.items():
        await _insert("conversations", {
            "id": conv_id, "todo_id": todo1_id, "purpose": purpose,
            "created_at": now - timedelta(days=10), "updated_at": now,
        })

    # Pipeline phases
    t1_phases_data = [
        ("clarification", "confirmed", t1_conv["clarification"]),
        ("ui_design", "awaiting_confirm", t1_conv["ui_design"]),
        ("architecture", "pending", None),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t1_phases_data:
        await _insert("pipeline_phases", {
            "id": t1_phase[pt], "todo_id": todo1_id,
            "phase_type": pt, "status": status, "conversation_id": cid,
            "created_at": now - timedelta(days=10), "updated_at": now,
        })

    # Messages
    await _insert_messages(t1_conv["clarification"], TODO1_CLAR_MESSAGES, now - timedelta(days=10))
    await _insert_messages(t1_conv["ui_design"], TODO1_UI_MESSAGES, now - timedelta(days=7))

    # Artifacts
    await _insert("artifacts", {
        "id": uuid.uuid4(), "todo_id": todo1_id, "phase_id": t1_phase["clarification"],
        "artifact_type": "requirement_spec", "content": json.dumps(TODO1_REQUIREMENT_SPEC),
        "version": 1, "is_confirmed": True, "confirmed_at": now - timedelta(days=8),
        "created_at": now - timedelta(days=10), "updated_at": now - timedelta(days=8),
    })
    await _insert("artifacts", {
        "id": uuid.uuid4(), "todo_id": todo1_id, "phase_id": t1_phase["ui_design"],
        "artifact_type": "ui_design", "content": json.dumps(TODO1_UI_DESIGN),
        "version": 1, "is_confirmed": False, "confirmed_at": None,
        "created_at": now - timedelta(days=6), "updated_at": now,
    })

    # ── Todo2: 用户权限与角色管理 (done, all phases completed) ──

    await _insert("todos", {
        "id": todo2_id, "user_id": user_id, "project_id": project1_id, "version_id": ver1_id,
        "title": "用户权限与角色管理",
        "description": "RBAC 权限模型，支持管理员/运营/只读三种角色，控制数据导出和看板访问权限",
        "status": "done", "priority": 1, "current_phase": "extraction",
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "安全", "color": "#EF4444"}]),
        "created_at": now - timedelta(days=18), "updated_at": now - timedelta(days=3),
    })

    # Conversations
    for purpose, conv_id in t2_conv.items():
        await _insert("conversations", {
            "id": conv_id, "todo_id": todo2_id, "purpose": purpose,
            "created_at": now - timedelta(days=18), "updated_at": now - timedelta(days=3),
        })

    # Step 1: Pipeline phases first (without agent_session_id, breaks circular FK)
    t2_phases_data = [
        ("clarification", "confirmed", t2_conv["clarification"]),
        ("ui_design", "confirmed", t2_conv["ui_design"]),
        ("architecture", "confirmed", t2_conv["architecture"]),
        ("development", "confirmed", None),
        ("testing", "confirmed", None),
        ("deployment", "confirmed", None),
        ("extraction", "confirmed", t2_conv["extraction"]),
    ]
    for pt, status, cid in t2_phases_data:
        await _insert("pipeline_phases", {
            "id": t2_phase[pt], "todo_id": todo2_id,
            "phase_type": pt, "status": status,
            "conversation_id": cid,
            "created_at": now - timedelta(days=18), "updated_at": now - timedelta(days=3),
        })

    # Step 2: Agent sessions (now pipeline_phases exist for FK)
    agent_sessions_data = [
        (t2_agent["development"], "development", "openhands", "completed",
         {"task": "实现RBAC权限体系：JWT鉴权中间件、角色装饰器、前端AuthContext和ProtectedRoute", "repo_url": "https://github.com/example/data-admin"},
         {"status": "success", "files_changed": 8, "tests_added": 27, "lines_added": 847, "lines_deleted": 23},
         now - timedelta(days=12), now - timedelta(days=12, hours=-2, minutes=-25)),
        (t2_agent["testing"], "testing", "openhands", "completed",
         {"task": "测试RBAC权限体系：认证流程、鉴权中间件、前端权限控制的自动化测试", "test_framework": "pytest + playwright"},
         {"status": "success", "total_tests": 27, "passed": 27, "failed": 0, "coverage_line": 89.2},
         now - timedelta(days=10), now - timedelta(days=10, hours=-1)),
        (t2_agent["deployment"], "deployment", "openhands", "completed",
         {"task": "部署RBAC权限体系：数据库迁移、后端服务更新、前端构建部署", "environment": "production"},
         {"status": "success", "migration_applied": True, "rollback_available": True},
         now - timedelta(days=8), now - timedelta(days=8, hours=-0, minutes=-30)),
    ]
    for sess_id, phase, agent_type, status, context, result, started, completed in agent_sessions_data:
        await _insert("agent_sessions", {
            "id": sess_id, "todo_id": todo2_id, "phase_id": t2_phase[phase],
            "agent_type": agent_type, "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
            "status": status, "task_context": json.dumps(context),
            "result_summary": json.dumps(result), "error_reason": "",
            "started_at": started, "completed_at": completed,
            "created_at": started, "updated_at": completed,
        })

    # Step 3: Backfill agent_session_id on pipeline_phases
    for phase_name, sess_id in t2_agent.items():
        await db.execute(
            text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
            {"aid": sess_id, "pid": t2_phase[phase_name]},
        )

    # Messages
    await _insert_messages(t2_conv["clarification"], TODO2_CLAR_MESSAGES, now - timedelta(days=18))
    await _insert_messages(t2_conv["ui_design"], TODO2_UI_MESSAGES, now - timedelta(days=16))
    await _insert_messages(t2_conv["architecture"], TODO2_ARCH_MESSAGES, now - timedelta(days=15))
    await _insert_messages(t2_conv["extraction"], TODO2_EXTRACT_MESSAGES, now - timedelta(days=4))

    # Artifacts (all 7 types)
    t2_artifacts = [
        ("requirement_spec", t2_phase["clarification"], TODO2_REQUIREMENT_SPEC, True, now - timedelta(days=17)),
        ("ui_design", t2_phase["ui_design"], TODO2_UI_DESIGN, True, now - timedelta(days=15)),
        ("tech_architecture", t2_phase["architecture"], TODO2_TECH_ARCHITECTURE, True, now - timedelta(days=14)),
        ("dev_report", t2_phase["development"], TODO2_DEV_REPORT, True, now - timedelta(days=11)),
        ("test_report", t2_phase["testing"], TODO2_TEST_REPORT, True, now - timedelta(days=9)),
        ("deploy_report", t2_phase["deployment"], TODO2_DEPLOY_REPORT, True, now - timedelta(days=7)),
        ("experience_card", t2_phase["extraction"], TODO2_EXPERIENCE_CARD, True, now - timedelta(days=4)),
    ]
    for art_type, phase_id, content, confirmed, conf_at in t2_artifacts:
        await _insert("artifacts", {
            "id": uuid.uuid4(), "todo_id": todo2_id, "phase_id": phase_id,
            "artifact_type": art_type, "content": json.dumps(content),
            "version": 1, "is_confirmed": confirmed, "confirmed_at": conf_at,
            "created_at": conf_at - timedelta(days=1), "updated_at": conf_at,
        })

    # ── Todo3: 导出任务队列与并发控制 (pending) ──

    await _insert("todos", {
        "id": todo3_id, "user_id": user_id, "project_id": project1_id, "version_id": ver1_id,
        "title": "导出任务队列与并发控制",
        "description": "基于 Celery 的异步任务队列，限制同时3个导出任务，支持任务状态查询和重试",
        "status": "pending", "priority": 2, "current_phase": None,
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "性能", "color": "#F59E0B"}]),
        "created_at": now - timedelta(days=7), "updated_at": now,
    })

    # ── Todo4 & Todo5: v1.1 planning todos ──

    v2_todos = [
        (todo4_id, "数据可视化看板",
         "用 ECharts 构建核心指标看板：日活、留存、转化漏斗，支持日期范围筛选",
         [{"label": "前端", "color": "#34D399"}, {"label": "可视化", "color": "#A78BFA"}]),
        (todo5_id, "定时导出与邮件通知",
         "支持配置周期性导出计划（日/周/月），导出完成后自动发送邮件通知",
         [{"label": "后端", "color": "#4A9FD8"}]),
    ]
    for i, (tid, title, desc, tags) in enumerate(v2_todos):
        await _insert("todos", {
            "id": tid, "user_id": user_id, "project_id": project1_id, "version_id": ver2_id,
            "title": title, "description": desc,
            "status": "pending", "priority": i + 2, "current_phase": None,
            "tags": json.dumps(tags),
            "created_at": now - timedelta(days=5), "updated_at": now - timedelta(days=5),
        })

    # ═══════════════════════════════════════════════════════════
    # Project 2: 智能客服系统
    # ═══════════════════════════════════════════════════════════

    await _insert("projects", {
        "id": project2_id, "user_id": user_id,
        "name": "智能客服系统",
        "description": "基于 RAG 的企业知识库客服，支持多轮对话和工单自动分流",
        "tech_stack": "Next.js + Python + Milvus + LangChain",
        "status": "active",
        "created_at": now - timedelta(days=14), "updated_at": now - timedelta(days=1),
    })

    await _insert("versions", {
        "id": ver3_id, "project_id": project2_id,
        "name": "v1.0", "goal": "知识库检索 + 多轮对话 + 客服工作台",
        "status": "active", "order": 1,
        "created_at": now - timedelta(days=14), "updated_at": now - timedelta(days=1),
    })

    # ── Todo6: 文档解析与向量化 (active, at architecture) ──

    await _insert("todos", {
        "id": todo6_id, "user_id": user_id, "project_id": project2_id, "version_id": ver3_id,
        "title": "文档解析与向量化",
        "description": "支持 PDF/Markdown 文档切片和 embedding，接入 Milvus 向量库",
        "status": "active", "priority": 1, "current_phase": "architecture",
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "AI", "color": "#A78BFA"}]),
        "created_at": now - timedelta(days=12), "updated_at": now - timedelta(days=1),
    })

    # Conversations
    for purpose, conv_id in t6_conv.items():
        await _insert("conversations", {
            "id": conv_id, "todo_id": todo6_id, "purpose": purpose,
            "created_at": now - timedelta(days=12), "updated_at": now,
        })

    # Pipeline phases
    t6_phases_data = [
        ("clarification", "confirmed", t6_conv["clarification"]),
        ("ui_design", "skipped", None),
        ("architecture", "active", t6_conv["architecture"]),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t6_phases_data:
        await _insert("pipeline_phases", {
            "id": t6_phase[pt], "todo_id": todo6_id,
            "phase_type": pt, "status": status, "conversation_id": cid,
            "created_at": now - timedelta(days=12), "updated_at": now,
        })

    # Messages
    await _insert_messages(t6_conv["clarification"], TODO6_CLAR_MESSAGES, now - timedelta(days=11))
    await _insert_messages(t6_conv["architecture"], TODO6_ARCH_MESSAGES, now - timedelta(days=6))

    # Artifacts
    await _insert("artifacts", {
        "id": uuid.uuid4(), "todo_id": todo6_id, "phase_id": t6_phase["clarification"],
        "artifact_type": "requirement_spec", "content": json.dumps(TODO6_REQUIREMENT_SPEC),
        "version": 1, "is_confirmed": True, "confirmed_at": now - timedelta(days=9),
        "created_at": now - timedelta(days=11), "updated_at": now - timedelta(days=9),
    })
    await _insert("artifacts", {
        "id": uuid.uuid4(), "todo_id": todo6_id, "phase_id": t6_phase["architecture"],
        "artifact_type": "tech_architecture", "content": json.dumps(TODO6_TECH_ARCHITECTURE),
        "version": 1, "is_confirmed": False, "confirmed_at": None,
        "created_at": now - timedelta(days=5), "updated_at": now,
    })

    # ── Todo7 & Todo8: pending todos ──

    p2_todos = [
        (todo7_id, "多轮对话管理",
         "维护对话上下文窗口，支持追问、澄清和话题切换，上下文窗口动态调整",
         [{"label": "后端", "color": "#4A9FD8"}]),
        (todo8_id, "客服工作台前端",
         "客服人员的实时会话列表、快捷回复模板和工单转接界面",
         [{"label": "前端", "color": "#34D399"}, {"label": "UX", "color": "#EC4899"}]),
    ]
    for tid, title, desc, tags in p2_todos:
        await _insert("todos", {
            "id": tid, "user_id": user_id, "project_id": project2_id, "version_id": ver3_id,
            "title": title, "description": desc,
            "status": "pending", "priority": 2, "current_phase": None,
            "tags": json.dumps(tags),
            "created_at": now - timedelta(days=12), "updated_at": now - timedelta(days=1),
        })

    # ═══════════════════════════════════════════════════════════
    # Project 3: 移动电商App
    # ═══════════════════════════════════════════════════════════

    project3_id = uuid.uuid4()
    ver4_id = uuid.uuid4()
    todo9_id, todo10_id = uuid.uuid4(), uuid.uuid4()
    t9_phase = {pt: uuid.uuid4() for pt in ["clarification", "ui_design", "architecture", "development", "testing", "deployment", "extraction"]}
    t9_conv = {"clarification": uuid.uuid4(), "ui_design": uuid.uuid4(), "architecture": uuid.uuid4()}
    t9_agent = {"development": uuid.uuid4()}

    await _insert("projects", {
        "id": project3_id, "user_id": user_id,
        "name": "移动电商App",
        "description": "C端电商移动应用，涵盖商品搜索、个性化推荐、订单管理和支付系统",
        "tech_stack": "React Native + Node.js + MongoDB + Elasticsearch + Redis",
        "status": "active",
        "created_at": now - timedelta(days=30), "updated_at": now - timedelta(days=1),
    })

    await _insert("versions", {
        "id": ver4_id, "project_id": project3_id,
        "name": "v1.0", "goal": "商品搜索优化 + 个性化推荐",
        "status": "active", "order": 1,
        "created_at": now - timedelta(days=30), "updated_at": now - timedelta(days=1),
    })

    # ── Todo9: 商品搜索优化 (active, at development) ──

    await _insert("todos", {
        "id": todo9_id, "user_id": user_id, "project_id": project3_id, "version_id": ver4_id,
        "title": "商品搜索优化",
        "description": "基于 Elasticsearch 重构搜索系统，支持中文分词、同义词扩展和搜索联想",
        "status": "active", "priority": 1, "current_phase": "development",
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "搜索", "color": "#F59E0B"}]),
        "created_at": now - timedelta(days=20), "updated_at": now - timedelta(days=1),
    })

    for purpose, conv_id in t9_conv.items():
        await _insert("conversations", {
            "id": conv_id, "todo_id": todo9_id, "purpose": purpose,
            "created_at": now - timedelta(days=20), "updated_at": now,
        })

    t9_phases_data = [
        ("clarification", "confirmed", t9_conv["clarification"]),
        ("ui_design", "confirmed", t9_conv["ui_design"]),
        ("architecture", "confirmed", t9_conv["architecture"]),
        ("development", "confirmed", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t9_phases_data:
        await _insert("pipeline_phases", {
            "id": t9_phase[pt], "todo_id": todo9_id,
            "phase_type": pt, "status": status, "conversation_id": cid,
            "created_at": now - timedelta(days=20), "updated_at": now,
        })

    # Agent session for development
    await _insert("agent_sessions", {
        "id": t9_agent["development"], "todo_id": todo9_id, "phase_id": t9_phase["development"],
        "agent_type": "openhands", "external_session_id": f"oh-{uuid.uuid4().hex[:12]}",
        "status": "completed", "task_context": json.dumps({
            "task": "基于Elasticsearch实现商品搜索：IK分词+同义词+联想词+筛选排序",
            "repo_url": "https://github.com/example/ecommerce-app",
        }),
        "result_summary": json.dumps({
            "status": "success", "files_changed": 7, "tests_added": 18,
            "lines_added": 1236, "lines_deleted": 89,
        }),
        "error_reason": "",
        "started_at": now - timedelta(days=3), "completed_at": now - timedelta(days=3, hours=-3),
        "created_at": now - timedelta(days=3), "updated_at": now - timedelta(days=3, hours=-3),
    })

    await db.execute(
        text("UPDATE pipeline_phases SET agent_session_id = :aid WHERE id = :pid"),
        {"aid": t9_agent["development"], "pid": t9_phase["development"]},
    )

    await _insert_messages(t9_conv["clarification"], TODO9_CLAR_MESSAGES, now - timedelta(days=18))
    await _insert_messages(t9_conv["ui_design"], TODO9_UI_MESSAGES, now - timedelta(days=14))
    await _insert_messages(t9_conv["architecture"], TODO9_ARCH_MESSAGES, now - timedelta(days=10))

    t9_artifacts = [
        ("requirement_spec", t9_phase["clarification"], TODO9_REQUIREMENT_SPEC, True, now - timedelta(days=16)),
        ("ui_design", t9_phase["ui_design"], TODO9_UI_DESIGN, True, now - timedelta(days=12)),
        ("tech_architecture", t9_phase["architecture"], TODO9_TECH_ARCHITECTURE, True, now - timedelta(days=8)),
        ("dev_report", t9_phase["development"], TODO9_DEV_REPORT, True, now - timedelta(days=2)),
    ]
    for art_type, phase_id, content, confirmed, conf_at in t9_artifacts:
        await _insert("artifacts", {
            "id": uuid.uuid4(), "todo_id": todo9_id, "phase_id": phase_id,
            "artifact_type": art_type, "content": json.dumps(content),
            "version": 1, "is_confirmed": confirmed, "confirmed_at": conf_at,
            "created_at": conf_at - timedelta(days=1), "updated_at": conf_at,
        })

    # ── Todo10: 个性化推荐算法 (pending) ──

    await _insert("todos", {
        "id": todo10_id, "user_id": user_id, "project_id": project3_id, "version_id": ver4_id,
        "title": "个性化推荐算法",
        "description": "基于用户行为数据的协同过滤推荐，首页千人千面和搜索结果个性化排序",
        "status": "pending", "priority": 2, "current_phase": None,
        "tags": json.dumps([{"label": "AI", "color": "#A78BFA"}, {"label": "推荐", "color": "#EC4899"}]),
        "created_at": now - timedelta(days=20), "updated_at": now - timedelta(days=1),
    })

    # ═══════════════════════════════════════════════════════════
    # Project 4: 内部OKR管理平台
    # ═══════════════════════════════════════════════════════════

    project4_id = uuid.uuid4()
    ver5_id = uuid.uuid4()
    todo11_id, todo12_id = uuid.uuid4(), uuid.uuid4()
    t11_phase = {pt: uuid.uuid4() for pt in ["clarification", "ui_design", "architecture", "development", "testing", "deployment", "extraction"]}
    t11_conv = {"clarification": uuid.uuid4()}

    await _insert("projects", {
        "id": project4_id, "user_id": user_id,
        "name": "内部OKR管理平台",
        "description": "支持目标对齐、进度追踪和复盘的OKR管理工具，替代飞书文档手工管理",
        "tech_stack": "Vue 3 + Go + MySQL + Redis",
        "status": "active",
        "created_at": now - timedelta(days=7), "updated_at": now - timedelta(days=1),
    })

    await _insert("versions", {
        "id": ver5_id, "project_id": project4_id,
        "name": "v1.0", "goal": "目标设定与可视化追踪",
        "status": "active", "order": 1,
        "created_at": now - timedelta(days=7), "updated_at": now - timedelta(days=1),
    })

    # ── Todo11: OKR目标树管理 (active, at clarification) ──

    await _insert("todos", {
        "id": todo11_id, "user_id": user_id, "project_id": project4_id, "version_id": ver5_id,
        "title": "OKR目标树管理",
        "description": "可视化目标树，支持O-KR层级展开、进度追踪、上下级对齐关系",
        "status": "active", "priority": 1, "current_phase": "clarification",
        "tags": json.dumps([{"label": "前端", "color": "#34D399"}, {"label": "核心功能", "color": "#6366F1"}]),
        "created_at": now - timedelta(days=5), "updated_at": now,
    })

    await _insert("conversations", {
        "id": t11_conv["clarification"], "todo_id": todo11_id, "purpose": "clarification",
        "created_at": now - timedelta(days=5), "updated_at": now,
    })

    t11_phases_data = [
        ("clarification", "active", t11_conv["clarification"]),
        ("ui_design", "pending", None),
        ("architecture", "pending", None),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for pt, status, cid in t11_phases_data:
        await _insert("pipeline_phases", {
            "id": t11_phase[pt], "todo_id": todo11_id,
            "phase_type": pt, "status": status, "conversation_id": cid,
            "created_at": now - timedelta(days=5), "updated_at": now,
        })

    await _insert_messages(t11_conv["clarification"], TODO11_CLAR_MESSAGES, now - timedelta(days=3))

    # ── Todo12: 进度自动同步 (pending) ──

    await _insert("todos", {
        "id": todo12_id, "user_id": user_id, "project_id": project4_id, "version_id": ver5_id,
        "title": "进度自动同步",
        "description": "KR进度与Jira/GitLab联动，自动计算完成百分比并同步到目标树",
        "status": "pending", "priority": 2, "current_phase": None,
        "tags": json.dumps([{"label": "后端", "color": "#4A9FD8"}, {"label": "集成", "color": "#F59E0B"}]),
        "created_at": now - timedelta(days=5), "updated_at": now,
    })

    # ═══════════════════════════════════════════════════════════
    # Project 5: 开发者开放平台 (3 versions, full pipeline)
    # ═══════════════════════════════════════════════════════════

    from seed_gateway import seed_gateway_project
    gw_result = await seed_gateway_project(db, user_id, now)
    project5_id = gw_result["project_id"]

    # ═══════════════════════════════════════════════════════════
    # Experiences
    # ═══════════════════════════════════════════════════════════

    todo_map = {"todo1": todo1_id, "todo2": todo2_id, "todo6": todo6_id}
    project_map = {"todo1": project1_id, "todo2": project1_id, "todo6": project2_id}

    exp_ids = []
    for exp in EXPERIENCES_DATA:
        eid = uuid.uuid4()
        exp_ids.append(eid)
        source = exp.pop("source_todo")
        await _insert("experiences", {
            "id": eid, "user_id": user_id,
            "todo_id": todo_map[source], "project_id": project_map[source],
            "title": exp["title"], "scope": exp["scope"], "status": exp["status"],
            "problem": exp["problem"], "solution": exp["solution"],
            "decisions": json.dumps(exp["decisions"]), "pitfalls": json.dumps(exp["pitfalls"]),
            "applicable_scenarios": exp["applicable_scenarios"],
            "tags": json.dumps(exp["tags"]),
            "confidence": exp["confidence"], "reuse_count": exp["reuse_count"],
            "created_at": now - timedelta(days=14), "updated_at": now - timedelta(days=2),
        })
        exp["source_todo"] = source

    # ═══════════════════════════════════════════════════════════
    # Experience Feedback
    # ═══════════════════════════════════════════════════════════

    feedback_data = [
        (exp_ids[0], todo1_id, True),
        (exp_ids[2], todo1_id, True),
        (exp_ids[3], todo1_id, True),
        (exp_ids[0], todo6_id, False),
    ]
    for eid, tid, helpful in feedback_data:
        await _insert("experience_feedback", {
            "id": uuid.uuid4(), "experience_id": eid, "todo_id": tid, "helpful": helpful,
            "created_at": now - timedelta(days=3), "updated_at": now - timedelta(days=3),
        })

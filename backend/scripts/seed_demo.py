"""Seed demo data for Arc pipeline demonstration.

Usage:
    python scripts/seed_demo.py

Inserts a complete todo with pipeline phases, conversations, messages,
artifacts (including the new Mermaid + HTML wireframe UI/UE artifact),
and experience records.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ── IDs (fixed for reproducibility) ──────────────────────────────────

TODO_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
PHASE_IDS = {
    "clarification": uuid.UUID("b0000000-0000-0000-0000-000000000001"),
    "ui_design": uuid.UUID("b0000000-0000-0000-0000-000000000002"),
    "architecture": uuid.UUID("b0000000-0000-0000-0000-000000000003"),
    "development": uuid.UUID("b0000000-0000-0000-0000-000000000004"),
    "testing": uuid.UUID("b0000000-0000-0000-0000-000000000005"),
    "deployment": uuid.UUID("b0000000-0000-0000-0000-000000000006"),
    "extraction": uuid.UUID("b0000000-0000-0000-0000-000000000007"),
}
CONV_IDS = {
    "clarification": uuid.UUID("c0000000-0000-0000-0000-000000000001"),
    "ui_design": uuid.UUID("c0000000-0000-0000-0000-000000000002"),
}
ARTIFACT_IDS = {
    "requirement_spec": uuid.UUID("d0000000-0000-0000-0000-000000000001"),
    "ui_design": uuid.UUID("d0000000-0000-0000-0000-000000000002"),
}
EXP_IDS = [
    uuid.UUID("e0000000-0000-0000-0000-000000000001"),
    uuid.UUID("e0000000-0000-0000-0000-000000000002"),
]

NOW = datetime.now(UTC)

# ── Artifact Content ─────────────────────────────────────────────────

REQUIREMENT_SPEC = {
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

UI_DESIGN_ARTIFACT = {
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
                '<div class="min-h-screen bg-gray-900 p-6">\n'
                '  <div class="max-w-4xl mx-auto">\n'
                '    <h1 class="text-xl font-bold text-white mb-6">数据导出</h1>\n'
                '    \n'
                '    <!-- 数据类型选择 -->\n'
                '    <div class="bg-gray-800 rounded-lg p-5 mb-4">\n'
                '      <h2 class="text-sm font-medium text-gray-400 mb-3">数据类型</h2>\n'
                '      <div class="flex gap-3">\n'
                '        <button class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm">'
                '用户行为</button>\n'
                '        <button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md text-sm">'
                '订单数据</button>\n'
                '        <button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md text-sm">'
                '商品数据</button>\n'
                '      </div>\n'
                '    </div>\n'
                '    \n'
                '    <!-- 筛选条件 -->\n'
                '    <div class="bg-gray-800 rounded-lg p-5 mb-4">\n'
                '      <h2 class="text-sm font-medium text-gray-400 mb-3">筛选条件</h2>\n'
                '      <div class="grid grid-cols-2 gap-4">\n'
                '        <div>\n'
                '          <label class="block text-xs text-gray-500 mb-1">开始日期</label>\n'
                '          <input type="date" value="2026-04-01" '
                'class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 '
                'text-sm text-white" />\n'
                '        </div>\n'
                '        <div>\n'
                '          <label class="block text-xs text-gray-500 mb-1">结束日期</label>\n'
                '          <input type="date" value="2026-04-30" '
                'class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 '
                'text-sm text-white" />\n'
                '        </div>\n'
                '        <div>\n'
                '          <label class="block text-xs text-gray-500 mb-1">用户类型</label>\n'
                '          <select class="w-full bg-gray-700 border border-gray-600 rounded '
                'px-3 py-2 text-sm text-white">\n'
                '            <option>全部</option>\n'
                '            <option>付费用户</option>\n'
                '            <option>免费用户</option>\n'
                '          </select>\n'
                '        </div>\n'
                '        <div>\n'
                '          <label class="block text-xs text-gray-500 mb-1">地区</label>\n'
                '          <select class="w-full bg-gray-700 border border-gray-600 rounded '
                'px-3 py-2 text-sm text-white">\n'
                '            <option>全部</option>\n'
                '            <option>华东</option>\n'
                '            <option>华北</option>\n'
                '            <option>华南</option>\n'
                '          </select>\n'
                '        </div>\n'
                '      </div>\n'
                '    </div>\n'
                '    \n'
                '    <!-- 数据预览 -->\n'
                '    <div class="bg-gray-800 rounded-lg p-5 mb-4">\n'
                '      <div class="flex items-center justify-between mb-3">\n'
                '        <h2 class="text-sm font-medium text-gray-400">'
                '数据预览 <span class="text-indigo-400">(匹配 87,432 条)</span></h2>\n'
                '        <button class="text-xs text-indigo-400 hover:text-indigo-300">'
                '刷新预览</button>\n'
                '      </div>\n'
                '      <div class="overflow-x-auto">\n'
                '        <table class="w-full text-left text-xs">\n'
                '          <thead>\n'
                '            <tr class="border-b border-gray-700 text-gray-500">\n'
                '              <th class="pb-2 pr-4">用户ID</th>\n'
                '              <th class="pb-2 pr-4">行为类型</th>\n'
                '              <th class="pb-2 pr-4">页面路径</th>\n'
                '              <th class="pb-2 pr-4">时间</th>\n'
                '              <th class="pb-2">设备</th>\n'
                '            </tr>\n'
                '          </thead>\n'
                '          <tbody class="text-gray-300">\n'
                '            <tr class="border-b border-gray-800">\n'
                '              <td class="py-2 pr-4 font-mono">u_38a21</td>\n'
                '              <td class="py-2 pr-4">页面浏览</td>\n'
                '              <td class="py-2 pr-4">/products/list</td>\n'
                '              <td class="py-2 pr-4">2026-04-15 09:32</td>\n'
                '              <td class="py-2">iOS</td>\n'
                '            </tr>\n'
                '            <tr class="border-b border-gray-800">\n'
                '              <td class="py-2 pr-4 font-mono">u_7bc43</td>\n'
                '              <td class="py-2 pr-4">按钮点击</td>\n'
                '              <td class="py-2 pr-4">/cart/checkout</td>\n'
                '              <td class="py-2 pr-4">2026-04-15 09:33</td>\n'
                '              <td class="py-2">Android</td>\n'
                '            </tr>\n'
                '            <tr>\n'
                '              <td class="py-2 pr-4 font-mono">u_11d05</td>\n'
                '              <td class="py-2 pr-4">页面浏览</td>\n'
                '              <td class="py-2 pr-4">/user/settings</td>\n'
                '              <td class="py-2 pr-4">2026-04-15 09:35</td>\n'
                '              <td class="py-2">Web</td>\n'
                '            </tr>\n'
                '          </tbody>\n'
                '        </table>\n'
                '      </div>\n'
                '      <p class="mt-2 text-xs text-gray-600">显示前 3 条 / 共 87,432 条</p>\n'
                '    </div>\n'
                '    \n'
                '    <!-- 操作按钮 -->\n'
                '    <div class="flex items-center justify-between">\n'
                '      <p class="text-xs text-gray-500">'
                '预计文件大小: ~12.3 MB  |  预计耗时: ~2 分钟</p>\n'
                '      <div class="flex gap-3">\n'
                '        <button class="px-4 py-2 bg-gray-700 text-gray-300 rounded-md '
                'text-sm">取消</button>\n'
                '        <button class="px-5 py-2 bg-indigo-600 text-white rounded-md '
                'text-sm font-medium">确认导出</button>\n'
                '      </div>\n'
                '    </div>\n'
                '  </div>\n'
                '</div>'
            ),
        },
        {
            "page_name": "导出历史页",
            "description": "展示历史导出记录、状态、下载链接",
            "html": (
                '<div class="min-h-screen bg-gray-900 p-6">\n'
                '  <div class="max-w-4xl mx-auto">\n'
                '    <h1 class="text-xl font-bold text-white mb-6">导出历史</h1>\n'
                '    \n'
                '    <div class="bg-gray-800 rounded-lg overflow-hidden">\n'
                '      <table class="w-full text-left text-sm">\n'
                '        <thead>\n'
                '          <tr class="border-b border-gray-700 text-xs text-gray-500 uppercase">\n'
                '            <th class="px-5 py-3">数据类型</th>\n'
                '            <th class="px-5 py-3">筛选条件</th>\n'
                '            <th class="px-5 py-3">数据量</th>\n'
                '            <th class="px-5 py-3">状态</th>\n'
                '            <th class="px-5 py-3">创建时间</th>\n'
                '            <th class="px-5 py-3">操作</th>\n'
                '          </tr>\n'
                '        </thead>\n'
                '        <tbody class="text-gray-300">\n'
                '          <tr class="border-b border-gray-800/50">\n'
                '            <td class="px-5 py-3">用户行为</td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-400">'
                '2026-04-01 ~ 04-30 | 付费用户</td>\n'
                '            <td class="px-5 py-3">87,432</td>\n'
                '            <td class="px-5 py-3">'
                '<span class="inline-flex items-center gap-1">'
                '<span class="w-2 h-2 rounded-full bg-green-500"></span>'
                '<span class="text-green-400 text-xs">完成</span></span></td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-500">2026-05-17 14:32</td>\n'
                '            <td class="px-5 py-3">'
                '<button class="text-indigo-400 text-xs hover:underline">下载</button></td>\n'
                '          </tr>\n'
                '          <tr class="border-b border-gray-800/50">\n'
                '            <td class="px-5 py-3">订单数据</td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-400">'
                '2026-03-01 ~ 03-31 | 全部</td>\n'
                '            <td class="px-5 py-3">23,891</td>\n'
                '            <td class="px-5 py-3">'
                '<span class="inline-flex items-center gap-1">'
                '<span class="w-2 h-2 rounded-full bg-yellow-500 animate-pulse"></span>'
                '<span class="text-yellow-400 text-xs">导出中...</span></span></td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-500">2026-05-17 14:58</td>\n'
                '            <td class="px-5 py-3">'
                '<span class="text-gray-600 text-xs">—</span></td>\n'
                '          </tr>\n'
                '          <tr>\n'
                '            <td class="px-5 py-3">用户行为</td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-400">'
                '2026-02-01 ~ 02-28 | 全部 | 华东</td>\n'
                '            <td class="px-5 py-3">512,003</td>\n'
                '            <td class="px-5 py-3">'
                '<span class="inline-flex items-center gap-1">'
                '<span class="w-2 h-2 rounded-full bg-red-500"></span>'
                '<span class="text-red-400 text-xs">失败</span></span></td>\n'
                '            <td class="px-5 py-3 text-xs text-gray-500">2026-05-16 10:15</td>\n'
                '            <td class="px-5 py-3">'
                '<button class="text-indigo-400 text-xs hover:underline">重试</button></td>\n'
                '          </tr>\n'
                '        </tbody>\n'
                '      </table>\n'
                '    </div>\n'
                '    \n'
                '    <p class="mt-4 text-xs text-gray-600">'
                '导出记录保留 30 天，过期文件将自动清理</p>\n'
                '  </div>\n'
                '</div>'
            ),
        },
    ],
    "component_specs": [
        {
            "name": "DataTypeSelector",
            "purpose": "数据类型切换（用户行为/订单/商品）",
            "behavior": "点击切换，高亮选中项，切换后重置筛选条件并刷新预览",
            "states": "default / selected / disabled(导出中)",
        },
        {
            "name": "FilterPanel",
            "purpose": "筛选条件面板（日期、用户类型、地区）",
            "behavior": "修改任一条件后自动刷新预览数据量，日期范围不超过6个月",
            "states": "default / loading(刷新中) / error(查询失败)",
        },
        {
            "name": "DataPreview",
            "purpose": "展示前20条数据预览和总匹配数",
            "behavior": "显示表格预览，超过50万行时显示警告并禁用导出按钮",
            "states": "empty / loading / loaded / over-limit",
        },
        {
            "name": "ExportButton",
            "purpose": "触发异步导出任务",
            "behavior": "点击后确认弹窗，确认后提交任务，按钮变为loading状态",
            "states": "default / loading / disabled(无数据或超限)",
        },
        {
            "name": "ExportHistoryTable",
            "purpose": "展示历史导出记录列表",
            "behavior": "按时间倒序，支持下载/重试操作，失败记录显示错误原因tooltip",
            "states": "empty / loaded",
        },
    ],
    "interaction_rules": (
        "1. 筛选条件变化后，防抖500ms再触发预览刷新\n"
        "2. 导出确认弹窗显示预估文件大小和耗时\n"
        "3. 导出中禁止修改当前配置，但可以查看历史\n"
        "4. 导出完成通过 WebSocket 推送通知，页面顶部显示toast\n"
        "5. 失败时显示具体错误原因，提供「重试」和「修改条件」两个操作"
    ),
    "responsive_notes": (
        "本功能仅在桌面端后台使用，最小支持宽度1024px。"
        "筛选条件区域在窄屏下从2列变为1列。"
        "数据预览表格支持横向滚动。"
    ),
}

# ── Conversation Messages ────────────────────────────────────────────

CLARIFICATION_MESSAGES = [
    ("assistant", "你好！我来帮你梳理「实现批量数据导出功能」的需求。\n\n"
     "先从问题本身开始——批量数据导出，这个需求主要想解决什么问题？"
     "目前用户遇到了哪些痛点？"),
    ("user", "运营团队每个月都要导出用户行为数据做分析报告，"
     "现在只能让开发人员直连数据库手动查出来，效率很低，"
     "而且直连数据库有安全风险。需要一个自助的导出功能。"),
    ("assistant", "明白了。核心问题是运营团队对数据的自助获取能力缺失，"
     "当前依赖开发资源且有安全隐患。\n\n"
     "追问几个细节：\n"
     "1. 需要导出的数据类型有哪些？只有用户行为，还是也包括订单、商品等？\n"
     "2. 数据量级大概多少？日均多少行？"),
    ("user", "数据类型主要三种：用户行为数据、订单数据、商品数据。"
     "用户行为是最大的，日均大概3-5万行，一个月下来差不多100万行。"
     "不过一般运营导出时会按条件筛选，实际导出量在10万行左右。"),
    ("assistant", "好的，信息很清晰。10万行级别的导出对性能有一定要求。\n\n"
     "现在推进到使用场景——描述一下运营人员的典型操作流程？"
     "他们从哪里进入，需要设置哪些筛选条件？"),
    ("user", "登录后台管理系统，进入数据导出页面，选择数据类型，"
     "然后设置日期范围和筛选条件比如用户类型、地区什么的，"
     "最好能先预览一下数据对不对，确认后再导出。"
     "导出应该是后台执行的，完成后通知我下载就行。"),
    ("assistant", "很好的场景描述。异步导出+通知的模式非常合理。\n\n"
     "关于边界和约束：\n"
     "1. 导出格式？CSV还是也要支持Excel？\n"
     "2. 单次导出有上限吗？\n"
     "3. 有没有时间节点的要求？"),
    ("user", "先只支持CSV就够了，Excel后面再考虑。"
     "单次上限50万行吧，再大了没有实际意义。"
     "下个月初要用，差不多两周内完成。"),
]

UI_DESIGN_MESSAGES = [
    ("assistant", "需求已经明确，现在来设计交互方案。\n\n"
     "我会产出 Mermaid 流程图和 HTML 线框图，让你能直观看到设计方案。\n"
     "「批量数据导出」的核心操作路径是什么？"
     "用户从哪里进入，经过哪些步骤，最终达到什么结果？"),
    ("user", "从后台侧边栏「数据管理」分类下进入「数据导出」页面。"
     "核心路径就是：选类型 → 设条件 → 预览 → 导出 → 等通知 → 下载。"
     "另外需要一个导出历史页面查看之前的导出记录。"),
    ("assistant", "好的，核心路径很清晰。我设计了两个页面：\n\n"
     "**页面1 - 数据导出配置页**\n"
     "- 顶部：数据类型切换（tab形式）\n"
     "- 中间：筛选条件面板（2列网格布局）\n"
     "- 下方：数据预览表格（前20条+总数）\n"
     "- 底部：导出按钮和预估信息\n\n"
     "**页面2 - 导出历史页**\n"
     "- 表格列出所有导出记录\n"
     "- 包含状态（排队中/导出中/完成/失败）\n"
     "- 完成的可下载，失败的可重试\n\n"
     "这个结构你觉得合理吗？"),
    ("user", "可以，就按这个来。注意预览数据量太大时要给提示，"
     "超过50万行直接禁止导出。"),
]


# ── Experience Data ──────────────────────────────────────────────────

EXPERIENCES = [
    {
        "id": EXP_IDS[0],
        "title": "大数据量CSV导出的流式写入方案",
        "problem": "一次性将10万行数据加载到内存生成CSV会导致OOM",
        "solution": (
            "采用分批查询+流式写入：每次从数据库查询5000行，"
            "逐批写入CSV文件，使用Python csv模块的writer逐行写入，"
            "内存占用恒定在~50MB以内"
        ),
        "decisions": [
            "选择分批大小5000行：太小影响速度，太大占内存",
            "使用原生csv模块而非pandas：避免引入重量级依赖",
        ],
        "pitfalls": [
            "CSV注入风险：以=、+、-、@开头的内容需要转义",
            "编码问题：需要显式指定UTF-8 BOM头，否则Excel打开中文乱码",
        ],
        "applicable_scenarios": "涉及大数据量文件生成的后台导出功能",
        "tags": [{"label": "性能优化", "color": "#10B981"},
                 {"label": "数据导出", "color": "#6366F1"}],
        "confidence": 0.82,
        "reuse_count": 3,
    },
    {
        "id": EXP_IDS[1],
        "title": "异步任务队列的并发控制设计",
        "problem": "多个用户同时触发导出任务会耗尽数据库连接和CPU资源",
        "solution": (
            "使用内存任务队列+信号量控制并发数为3。"
            "超出的任务排队等待，前端通过WebSocket实时推送任务状态变化"
        ),
        "decisions": [
            "选择内存队列而非Redis：单机场景不需要分布式，减少依赖",
            "并发数设为3：基于服务器4核CPU的经验值",
        ],
        "pitfalls": [
            "内存队列在服务重启时丢失：需要将任务状态持久化到数据库",
            "WebSocket断连后用户收不到通知：需要轮询兜底",
        ],
        "applicable_scenarios": "后台异步任务处理，涉及资源限制的场景",
        "tags": [{"label": "架构设计", "color": "#F59E0B"},
                 {"label": "并发控制", "color": "#EF4444"}],
        "confidence": 0.75,
        "reuse_count": 1,
    },
]


async def seed(db: AsyncSession) -> None:
    """Insert all demo data."""

    # Clean up existing demo data (child tables first due to FK constraints)
    await db.execute(
        text("DELETE FROM messages WHERE conversation_id = ANY(:ids)"),
        {"ids": list(CONV_IDS.values())},
    )
    await db.execute(
        text("DELETE FROM artifacts WHERE todo_id = :tid"),
        {"tid": TODO_ID},
    )
    await db.execute(
        text("DELETE FROM pipeline_phases WHERE todo_id = :tid"),
        {"tid": TODO_ID},
    )
    await db.execute(
        text("DELETE FROM conversations WHERE todo_id = :tid"),
        {"tid": TODO_ID},
    )
    await db.execute(
        text("DELETE FROM experiences WHERE id = ANY(:ids)"),
        {"ids": list(EXP_IDS)},
    )
    await db.execute(
        text("DELETE FROM todos WHERE id = :tid"),
        {"tid": TODO_ID},
    )

    # 1. Todo
    await db.execute(text("""
        INSERT INTO todos (id, title, description, status, current_phase, created_at, updated_at)
        VALUES (:id, :title, :desc, :status, :phase, :ca, :ua)
    """), {
        "id": TODO_ID,
        "title": "实现批量数据导出功能",
        "desc": "支持管理员按日期范围导出用户数据为CSV，异步执行+通知",
        "status": "active",
        "phase": "ui_design",
        "ca": NOW - timedelta(days=2),
        "ua": NOW,
    })

    # 2. Conversations
    for purpose, conv_id in CONV_IDS.items():
        await db.execute(text("""
            INSERT INTO conversations (id, todo_id, purpose, created_at, updated_at)
            VALUES (:id, :tid, :purpose, :ca, :ua)
        """), {
            "id": conv_id, "tid": TODO_ID, "purpose": purpose,
            "ca": NOW - timedelta(days=2), "ua": NOW,
        })

    # 3. Messages
    messages_map = {
        "clarification": CLARIFICATION_MESSAGES,
        "ui_design": UI_DESIGN_MESSAGES,
    }
    for purpose, msgs in messages_map.items():
        conv_id = CONV_IDS[purpose]
        base_time = NOW - timedelta(days=2 if purpose == "clarification" else 1)
        for i, (role, content) in enumerate(msgs):
            await db.execute(text("""
                INSERT INTO messages (id, conversation_id, role, content, created_at)
                VALUES (:id, :cid, :role, :content, :ca)
            """), {
                "id": uuid.uuid4(),
                "cid": conv_id,
                "role": role,
                "content": content,
                "ca": base_time + timedelta(minutes=i * 3),
            })

    # 4. Pipeline phases
    phase_configs = [
        ("clarification", "confirmed", CONV_IDS["clarification"]),
        ("ui_design", "awaiting_confirm", CONV_IDS["ui_design"]),
        ("architecture", "pending", None),
        ("development", "pending", None),
        ("testing", "pending", None),
        ("deployment", "pending", None),
        ("extraction", "pending", None),
    ]
    for phase_type, status, conv_id in phase_configs:
        await db.execute(text("""
            INSERT INTO pipeline_phases
                (id, todo_id, phase_type, status, conversation_id, created_at, updated_at)
            VALUES (:id, :tid, :pt, :status, :cid, :ca, :ua)
        """), {
            "id": PHASE_IDS[phase_type],
            "tid": TODO_ID,
            "pt": phase_type,
            "status": status,
            "cid": conv_id,
            "ca": NOW - timedelta(days=2),
            "ua": NOW,
        })

    # 5. Artifacts
    import json
    await db.execute(text("""
        INSERT INTO artifacts
            (id, todo_id, phase_id, artifact_type, content, version, is_confirmed,
             confirmed_at, created_at, updated_at)
        VALUES (:id, :tid, :pid, :at, :content, :ver, :confirmed, :ca_at, :ca, :ua)
    """), {
        "id": ARTIFACT_IDS["requirement_spec"],
        "tid": TODO_ID,
        "pid": PHASE_IDS["clarification"],
        "at": "requirement_spec",
        "content": json.dumps(REQUIREMENT_SPEC),
        "ver": 1,
        "confirmed": True,
        "ca_at": NOW - timedelta(days=1),
        "ca": NOW - timedelta(days=2),
        "ua": NOW - timedelta(days=1),
    })

    await db.execute(text("""
        INSERT INTO artifacts
            (id, todo_id, phase_id, artifact_type, content, version, is_confirmed,
             confirmed_at, created_at, updated_at)
        VALUES (:id, :tid, :pid, :at, :content, :ver, :confirmed, :ca_at, :ca, :ua)
    """), {
        "id": ARTIFACT_IDS["ui_design"],
        "tid": TODO_ID,
        "pid": PHASE_IDS["ui_design"],
        "at": "ui_design",
        "content": json.dumps(UI_DESIGN_ARTIFACT),
        "ver": 1,
        "confirmed": False,
        "ca_at": None,
        "ca": NOW - timedelta(hours=6),
        "ua": NOW,
    })

    # 6. Experiences
    for exp in EXPERIENCES:
        await db.execute(text("""
            INSERT INTO experiences
                (id, todo_id, title, problem, solution, decisions, pitfalls,
                 applicable_scenarios, tags, confidence, reuse_count,
                 created_at, updated_at)
            VALUES (:id, :tid, :title, :problem, :solution, :decisions, :pitfalls,
                    :scenarios, :tags, :confidence, :reuse, :ca, :ua)
        """), {
            "id": exp["id"],
            "tid": TODO_ID,
            "title": exp["title"],
            "problem": exp["problem"],
            "solution": exp["solution"],
            "decisions": json.dumps(exp["decisions"]),
            "pitfalls": json.dumps(exp["pitfalls"]),
            "scenarios": exp["applicable_scenarios"],
            "tags": json.dumps(exp["tags"]),
            "confidence": exp["confidence"],
            "reuse": exp["reuse_count"],
            "ca": NOW - timedelta(days=7),
            "ua": NOW - timedelta(days=1),
        })

    await db.commit()
    print(f"Demo data seeded successfully!")
    print(f"  Todo:          {TODO_ID}")
    print(f"  Phases:        7 (clarification=confirmed, ui_design=awaiting_confirm)")
    print(f"  Artifacts:     2 (requirement_spec, ui_design with Mermaid+wireframes)")
    print(f"  Conversations: 2 ({sum(len(v) for v in messages_map.values())} messages)")
    print(f"  Experiences:   2")


async def main():
    from arc.infrastructure.database import async_session_factory
    async with async_session_factory() as db:
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())

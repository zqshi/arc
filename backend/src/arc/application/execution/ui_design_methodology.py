"""UI/交互设计方法论引擎 — 基于 frontend-design + ui-ux-pro-max 改造。

来源:
  - anthropics/skills/frontend-design: 设计思维框架 + 美学标准 + 反模式
  - ui-ux-pro-max: 行业推理规则 + 预交付检查清单
职责:
  - 引导 UI 设计阶段按"设计思维→信息架构→线框→可用性自检"递进
  - 注入美学标准和行业反模式避免
  - 提供预交付质量检查清单
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 设计思维框架 (来自 anthropics/frontend-design SKILL.md)
# ---------------------------------------------------------------------------

DESIGN_THINKING_PROMPT = """\
## 设计方法论: 交互设计四步递进

**当前阶段**: {current_stage}

### Step 1: 设计思维 (Design Thinking)
在动手画线框之前，先回答:
- **目的**: 这个界面解决什么问题？谁在用？
- **调性**: 选定一个明确的美学方向（简约克制 / 信息密集 / 活泼有趣 / 专业严肃 / 极简留白）
- **约束**: 技术框架、性能要求、无障碍要求
- **差异化**: 什么让这个界面令人记住？核心视觉锚点是什么？

### Step 2: 信息架构 (Information Architecture)
基于需求规格中的 user_scenarios:
- 绘制用户旅程地图 — 用户从哪进入、经过哪些步骤、到达什么终态
- 定义页面层级和导航结构
- 确定信息优先级 — 用户最先看到什么、最常操作什么

### Step 3: 原型工程 (Prototype Engineering)
逐页面设计后，使用工具创建完整的前端工程:
- 使用 write_file 创建 Vite + React + Tailwind 项目
- 每个线框页面对应一个路由页面组件
- 使用 HashRouter 实现页面间真实导航
- 共享 Layout（Header/Sidebar）组件，页面切换只替换内容区
- 使用 Zustand store 管理 Mock 数据和全局状态
- 创建完成后执行 npm install && npm run build
- **不要生成 HTML 片段，要生成可构建的工程代码**

### Step 4: 可用性自检 (Usability Heuristics)
对照 Nielsen 10 启发式原则自检:
1. 系统状态可见性 — 用户知道当前在哪、在做什么吗？
2. 匹配现实世界 — 用的词和概念是用户熟悉的吗？
3. 用户控制与自由 — 有撤销、返回、取消吗？
4. 一致性与标准 — 同类操作的交互一致吗？
5. 错误预防 — 关键操作有确认步骤吗？
6. 识别而非回忆 — 关键信息可见还是需要记住？
7. 灵活性与效率 — 高频操作有快捷路径吗？
8. 美学与极简 — 每个元素都有存在的理由吗？
9. 帮助用户识别错误 — 错误提示明确指出问题和解法吗？
10. 帮助与文档 — 复杂操作有引导吗？

### 反模式 (Anti-patterns) — 避免以下常见问题:
- ❌ 没有空状态设计（第一次使用时茫然）
- ❌ 没有加载态（用户不知道在等什么）
- ❌ 表单没有即时验证（提交后才告诉哪错了）
- ❌ 关键操作没有确认步骤（误点不可逆）
- ❌ 信息层级不清（什么都一样大一样重要）
- ❌ 移动端适配缺失（桌面设计硬缩放）
"""

# ---------------------------------------------------------------------------
# 预交付检查清单 (来自 ui-ux-pro-max 概念)
# ---------------------------------------------------------------------------

UI_DESIGN_CHECKLIST = [
    "每个 user_scenario 是否有对应的路由页面",
    "是否使用 HashRouter 实现客户端路由",
    "是否有共享 Layout 组件（Header/Sidebar 不重复渲染）",
    "是否定义了空状态、加载态、异常态",
    "核心操作路径是否在 3 步以内完成",
    "是否有 Zustand store 管理全局状态和 Mock 数据",
    "页面间是否有真实数据流（列表→详情、表单→提交→反馈）",
    "是否通过 Nielsen 10 启发式自检",
    "移动端是否有响应式适配",
    "npm run build 是否成功通过",
]


def get_ui_design_prompt(conversation_round: int) -> str:
    """根据对话轮次返回当前阶段 prompt。"""
    if conversation_round < 2:
        stage = "Step 1: 设计思维 — 确定调性和约束"
    elif conversation_round < 4:
        stage = "Step 2: 信息架构 — 用户旅程和页面层级"
    elif conversation_round < 8:
        stage = "Step 3: 原型工程 — 创建 Vite+React 前端工程"
    else:
        stage = "Step 4: 可用性自检 — Nielsen 启发式 + 检查清单"
    return DESIGN_THINKING_PROMPT.format(current_stage=stage)


def validate_ui_design(content: dict) -> list[str]:
    """UI 设计产出物质量校验。"""
    gaps = []

    wireframes = content.get("wireframes", [])
    component_specs = content.get("component_specs", [])

    # 检查线框是否标注了 story 关联
    if wireframes:
        for wf in wireframes:
            if isinstance(wf, dict) and not wf.get("story_id") and not wf.get("user_story"):
                name = wf.get("page_name", "未命名")
                gaps.append(f"线框「{name}」未标注关联的 user_story")

    # 检查是否定义了状态
    has_empty_state = False
    has_loading_state = False
    has_error_state = False
    for comp in component_specs:
        if not isinstance(comp, dict):
            continue
        states = comp.get("states", "")
        if "空" in states or "empty" in states.lower():
            has_empty_state = True
        if "加载" in states or "loading" in states.lower():
            has_loading_state = True
        if "错误" in states or "error" in states.lower():
            has_error_state = True

    if wireframes and not has_empty_state:
        gaps.append("未定义空状态设计")
    if wireframes and not has_loading_state:
        gaps.append("未定义加载状态")

    return gaps

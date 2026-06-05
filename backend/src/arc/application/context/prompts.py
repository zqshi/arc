"""对话驱动执行模式的系统提示词和产出物定义。

设计哲学：意图驱动，Agent 自主推理。
- prompt 只给目标 + 能力声明 + 上下文
- Agent 自主决定推进路径、产出时机、分析深度
- 质量通过输出接口契约 + 后置验证保障，不通过前置规则约束
"""

from __future__ import annotations

from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType

ARTIFACT_TYPE_MARKERS: dict[str, ArtifactType] = {
    "requirement_spec": ArtifactType.REQUIREMENT_SPEC,
    "interaction_design": ArtifactType.INTERACTION_DESIGN,
    "ui_spec": ArtifactType.UI_SPEC,
    "prototype": ArtifactType.PROTOTYPE,
    "tech_architecture": ArtifactType.TECH_ARCHITECTURE,
    "dev_report": ArtifactType.DEV_REPORT,
    "test_report": ArtifactType.TEST_REPORT,
    "deploy_report": ArtifactType.DEPLOY_REPORT,
    "experience_card": ArtifactType.EXPERIENCE_CARD,
    # Legacy
    "ui_design": ArtifactType.UI_DESIGN,
}

DELIVERABLE_CHECKLIST_TEMPLATE = """## 交付物清单
{checklist}

当你判断某个交付物可以产出时，使用以下格式：

[DELIVERABLE:{artifact_type}]
```json
{{结构化内容}}
```

系统会自动解析归档。用户可在侧边面板查看已归档产出物。"""


def build_deliverable_checklist(required: list[str], completed: list[str]) -> str:
    lines = []
    for atype in required:
        label = ARTIFACT_LABELS.get(ArtifactType(atype), atype)
        marker = "x" if atype in completed else " "
        lines.append(f"- [{marker}] {label}")
    return "\n".join(lines)


CONVERSATION_MODE_SYSTEM_PROMPT = """你正在帮用户完成「{title}」。

目标：作为搭档，把这个需求从想法推进到可交付的成果。你自主判断需要做什么、什么时候做、怎么做。

{deliverable_section}

{methodology_section}

{project_context}

{experience_context}

{sufficiency_hint}

## 当前任务
标题: {title}
描述: {description}

## 已完成的交付物
{completed_artifacts}"""


AUTOPILOT_SECTION = """## 自驾模式
你可以自主推进所有交付物，无需等待确认。只有在遇到真正无法独立决策的分歧点时才暂停（输出 [NEEDS_INPUT]）。"""


# ---------------------------------------------------------------------------
# 交付物 JSON Schema（输出接口契约 — 不是规则，是让代码能解析的格式定义）
# ---------------------------------------------------------------------------

ARTIFACT_SCHEMAS: dict[str, str] = {
    "requirement_spec": """{
  "background": "需求背景和问题描述",
  "target_users": [
    {"type": "用户类型", "traits": "关键特征", "core_need": "核心诉求"}
  ],
  "core_value": {
    "user_value": "用户价值",
    "business_value": "业务价值",
    "tech_value": "技术价值"
  },
  "user_stories": [
    {"role": "角色", "goal": "目标", "benefit": "收益",
     "priority": "P0/P1/P2", "acceptance": "验收条件"}
  ],
  "user_scenarios": "典型使用场景和交互流程",
  "boundaries": {
    "in_scope": ["明确要做的"],
    "out_of_scope": ["明确不做的"],
    "constraints": ["技术/业务/合规约束"]
  },
  "acceptance_criteria": [
    {"id": "AC-1", "scenario": "场景", "steps": "操作步骤",
     "expected": "预期结果", "priority": "P0/P1/P2"}
  ],
  "risk_assessment": [
    {"risk": "风险描述", "probability": "高/中/低",
     "impact": "高/中/低", "mitigation": "应对策略"}
  ],
  "assumptions": [
    {"assumption": "假设内容", "confidence": "高/中/低",
     "validation_method": "验证方式"}
  ]
}""",
    "interaction_design": """{
  "user_flows": [
    {"name": "流程名称", "description": "流程描述",
     "mermaid": "graph TD/LR 完整Mermaid代码"}
  ],
  "page_map": [
    {"page": "页面名", "entry_from": "从哪进入",
     "exits_to": ["可跳转的页面"], "triggers": "触发条件"}
  ],
  "interaction_rules": [
    {"component": "组件/区域", "action": "用户操作",
     "response": "系统响应", "feedback": "反馈方式"}
  ],
  "error_flows": [
    {"scenario": "异常场景", "handling": "处理方式",
     "user_message": "用户提示"}
  ],
  "state_definitions": [
    {"page": "页面名", "states": ["空态", "加载中", "有数据", "错误"],
     "transitions": "状态转换说明"}
  ]
}""",
    "ui_spec": """{
  "design_tokens": {
    "colors": {"primary": "", "secondary": "", "accent": "",
               "background": "", "surface": "", "error": ""},
    "typography": {
      "heading": {"font": "", "sizes": ""},
      "body": {"font": "", "sizes": ""},
      "mono": {"font": "", "sizes": ""}
    },
    "spacing": {"unit": 4, "scale": [4, 8, 12, 16, 24, 32, 48]},
    "radius": {"sm": "", "md": "", "lg": ""},
    "shadows": {"sm": "", "md": "", "lg": ""}
  },
  "component_specs": [
    {"name": "组件名", "variants": ["变体"],
     "states": ["默认", "悬浮", "按下", "禁用"],
     "sizing": "尺寸规范", "usage": "使用场景"}
  ],
  "layout_grid": {
    "columns": 12,
    "gutter": "间距",
    "breakpoints": {"mobile": "", "tablet": "", "desktop": ""}
  },
  "iconography": "图标风格说明",
  "motion": "动效原则"
}""",
    "prototype": """{
  "project_dir": "prototype",
  "tech_stack": "vite-react-tailwind",
  "routes": [
    {"path": "/", "name": "首页", "component": "src/pages/Home.tsx"},
    {"path": "/login", "name": "登录", "component": "src/pages/Login.tsx"}
  ],
  "shared_state": ["user", "theme"],
  "build_status": "success",
  "build_command": "npm run build",
  "artifact_path": "dist"
}""",
    "tech_architecture": """{
  "architecture_overview": "整体架构描述",
  "domain_design": {
    "subdomains": [
      {"name": "子域名称", "type": "核心域|支撑域|通用域", "description": "职责描述"}
    ],
    "bounded_contexts": [
      {"name": "上下文名称", "subdomain": "所属子域", "description": "边界与职责"}
    ],
    "context_relations": [
      {"from": "上游上下文", "to": "下游上下文", "type": "协作模式", "description": "说明"}
    ]
  },
  "data_model": {
    "entities": [
      {"name": "实体名",
       "fields": [{"name": "", "type": "", "required": true, "description": ""}],
       "relations": "与其他实体的关系",
       "bounded_context": "所属限界上下文"}
    ],
    "erd_description": "实体关系概述"
  },
  "event_storming": {
    "events": [
      {"name": "领域事件名", "context": "所属上下文",
       "trigger": "触发方式", "actor": "触发角色", "aggregate": "关联聚合"}
    ],
    "commands": [
      {"name": "命令名", "actor": "操作角色",
       "target_aggregate": "目标聚合", "events_produced": ["产生的事件"]}
    ]
  },
  "api_design": [
    {"method": "HTTP方法", "path": "/api/路径",
     "description": "接口说明",
     "request_params": ["参数说明"],
     "response_example": "响应示例"}
  ],
  "tech_decisions": [
    {"decision": "决策点",
     "options_considered": ["方案A", "方案B"],
     "chosen": "选择的方案", "reason": "选择理由",
     "trade_offs": "代价与取舍"}
  ],
  "implementation_plan": [
    {"step": "步骤名", "description": "详细描述",
     "estimated_effort": "预估工作量", "priority": "P0/P1/P2"}
  ],
  "non_functional": {
    "performance": "性能要求和方案",
    "security": "安全要求和方案",
    "scalability": "可扩展性考虑"
  }
}""",
    "dev_report": """{
  "methodology": "ddd_tdd 或 lightweight",
  "test_design": {
    "derived_from": ["引用的验收标准ID"],
    "test_cases": [
      {"name": "测试名称", "type": "unit|integration|acceptance",
       "target_aggregate": "所属聚合",
       "given": "前置条件", "when": "操作", "then": "断言",
       "status": "pass|fail|pending"}
    ]
  },
  "implementation": {
    "aggregates_touched": ["聚合名"],
    "code_changes": [
      {"file": "文件路径", "change_type": "add|modify|delete",
       "description": "变更说明", "aggregate": "所属聚合"}
    ],
    "invariants_enforced": ["不变量描述"]
  },
  "validation": {
    "all_tests_pass": true,
    "coverage_notes": "覆盖说明",
    "refactoring_done": ["重构项"]
  },
  "decisions_made": [
    {"decision": "决策点", "reason": "原因"}
  ]
}""",
    "test_report": """{
  "criteria_verification": [
    {"criteria": "", "status": "pass/fail", "evidence": ""}
  ],
  "issues_found": [
    {"description": "", "severity": "high/medium/low", "suggestion": ""}
  ],
  "coverage_summary": "覆盖总结"
}""",
    "deploy_report": """{
  "deploy_log": {
    "environment": "部署目标环境 (dev/staging/production)",
    "method": "部署方式 (CI/CD / 手动 / 脚本)",
    "steps_executed": [
      {"step": "步骤名", "status": "success/failed", "output": "关键输出"}
    ],
    "duration_seconds": 0
  },
  "health_check_result": {
    "endpoints_checked": [
      {"url": "/api/health", "status": 200, "latency_ms": 0}
    ],
    "all_passed": true
  },
  "rollback_plan": "回滚方案描述",
  "config_changes": [
    {"key": "配置项", "old_value": "旧值", "new_value": "新值", "reason": "变更原因"}
  ],
  "release_notes": "面向用户的版本说明"
}""",
    "experience_card": """{
  "problem": "解决了什么问题",
  "solution": "最终方案",
  "decisions": [
    {"point": "决策点", "options_considered": ["方案A", "方案B"],
     "chosen": "选择的方案", "reason": "选择理由", "outcome": "实际效果"}
  ],
  "pitfalls": [
    {"issue": "遇到的问题", "cause": "根因分析",
     "fix": "修复方式", "prevention": "如何预防"}
  ],
  "applicable_scenarios": "适用场景",
  "reuse_checklist": ["复用前需要检查的条件"],
  "tags": ["标签"]
}""",
}


# ---------------------------------------------------------------------------
# 领域模型上下文注入（只提供事实，不提供指令）
# ---------------------------------------------------------------------------


def build_ddd_tdd_section(domain_model: dict) -> str:
    """将项目领域模型作为上下文注入，供 Agent 自行判断如何使用。"""
    aggregates = domain_model.get("aggregates", [])
    relations = domain_model.get("relations", [])
    subdomains = domain_model.get("subdomains", [])
    contexts = domain_model.get("contexts", [])
    aggregate_relations = domain_model.get("aggregate_relations", [])

    if len(aggregates) < 2 and not subdomains:
        return ""

    # 模型元信息 — 版本和来源
    version = domain_model.get("version", "unknown")
    source = domain_model.get("source", "artifact_extraction")
    updated_at = domain_model.get("updated_at", "")

    lines = [f"## 项目领域模型（{len(aggregates)} 聚合, {len(subdomains)} 子域, {len(contexts)} 上下文 | v{version}, 来源: {source}）"]
    if updated_at:
        lines.append(f"*最后更新: {updated_at}*\n")

    if subdomains:
        lines.append("\n### 子域")
        for sd in subdomains:
            lines.append(f"- {sd.get('name', '')} ({sd.get('type', '')}): {sd.get('description', '')}")

    if contexts:
        lines.append("\n### 限界上下文")
        for ctx in contexts:
            line = f"- {ctx.get('name', '')}"
            if ctx.get("subdomain"):
                line += f" → {ctx['subdomain']}"
            if ctx.get("description"):
                line += f": {ctx['description']}"
            lines.append(line)

    if relations:
        lines.append("\n### 上下文关系")
        for rel in relations:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    if aggregates:
        lines.append("\n### 聚合")
        for agg in aggregates[:20]:
            name = agg.get("name", "")
            ctx = agg.get("context", "")
            parts = []
            if agg.get("entities"):
                parts.append(f"实体: {', '.join(agg['entities'][:5])}")
            if agg.get("value_objects"):
                parts.append(f"值对象: {', '.join(agg['value_objects'][:5])}")
            if agg.get("methods"):
                parts.append(f"方法: {', '.join(agg['methods'][:5])}")
            detail = "; ".join(parts) if parts else ""
            line = f"- **{name}**"
            if ctx:
                line += f" ({ctx})"
            if detail:
                line += f" — {detail}"
            lines.append(line)

    if aggregate_relations:
        lines.append("\n### 聚合关系")
        for rel in aggregate_relations[:15]:
            lines.append(f"- {rel.get('from', '')} → {rel.get('to', '')} [{rel.get('type', '')}]")

    # 附加参考模式——Agent 根据项目实际情况自行选用
    lines.append("\n### 可参考的架构模式")
    lines.append(_REFERENCE_PATTERNS)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 参考模式库 — 作为上下文提供，Agent 自行判断适用性
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 原型工程化指导 — 告诉 AI 生成真实前端工程而非 HTML 片段
# ---------------------------------------------------------------------------

PROTOTYPE_ENGINEERING_PROMPT = """\
## 原型工程要求

当需要产出原型时，你需要使用 write_file 工具在项目目录下创建一个**完整的前端工程**（不是 HTML 片段）。

### 目录结构

```
prototype/
├── package.json          # vite + react + react-router-dom + tailwindcss + zustand
├── vite.config.ts        # base: './' (相对路径，S3兼容)
├── tailwind.config.js
├── postcss.config.js
├── index.html            # 入口 HTML
├── src/
│   ├── main.tsx          # createRoot + HashRouter 挂载
│   ├── App.tsx           # 路由表 + 全局 Layout
│   ├── store.ts          # Zustand 状态 (用户、主题、Mock数据)
│   ├── pages/            # 每个路由一个页面组件
│   │   ├── Home.tsx
│   │   ├── Login.tsx
│   │   └── ...
│   ├── components/       # 共享组件 (Header, Sidebar, Modal, Toast)
│   │   ├── Layout.tsx
│   │   └── ...
│   └── styles/
│       └── index.css     # @tailwind base/components/utilities
```

### 关键约束

1. **HashRouter** — 使用 `createHashRouter`，S3 静态托管无需服务端路由
2. **共享 Layout** — Header/Sidebar/Footer 在 Layout 组件中，页面切换只替换内容区
3. **真实数据流** — 用 Zustand store 存 Mock 数据，列表→详情、表单→提交→反馈 全部可交互
4. **交互真实** — 按钮有 loading/disabled 状态、表单有即时校验、Toast 通知、Modal 确认
5. **状态持久** — 登录后导航栏变化、列表操作后数据更新，跨页面状态一致
6. **构建命令** — 完成所有文件后执行: `cd prototype && npm install && npm run build`
7. **Vite base** — vite.config.ts 中设置 `base: './'`（部署到 S3 子路径时路径正确）

### 产出格式

文件创建并构建成功后，输出 [DELIVERABLE:prototype] 包含工程清单 JSON（不是 HTML）:
```json
{
  "project_dir": "prototype",
  "tech_stack": "vite-react-tailwind",
  "routes": [{"path": "/", "name": "首页", "component": "src/pages/Home.tsx"}, ...],
  "shared_state": ["user", "currentProject", ...],
  "build_status": "success",
  "build_command": "npm run build",
  "artifact_path": "dist"
}
```

### 设计原则

- 像做真实产品一样做原型：用户拿到这个 URL 应该能体验到完整的产品交互
- 视觉用 Tailwind 实现，深色主题为主，风格现代简洁
- 移动端响应式（至少不崩溃）
- 组件粒度合理：不要把一个页面写 500 行，拆子组件
"""


_REFERENCE_PATTERNS = """\
以下模式供参考，根据项目实际情况选用最合适的：

**DDD（领域驱动设计）** — 适合业务逻辑复杂、有明确领域概念的系统
- 聚合 = 事务一致性边界，聚合间 ID 引用
- 值对象优先（不可变 = 安全）
- 限界上下文间通过 ACL/OHS/事件协作
- 领域事件驱动跨上下文通信

**TDD（测试驱动开发）** — 适合有明确验收标准、需要高可靠性的交付
- 从验收标准派生测试用例
- Red → Green → Refactor
- 每个测试对应一个业务不变量

**Clean Architecture** — 适合需要长期维护、技术栈可能变更的系统
- 依赖方向：外层 → 内层
- domain 不依赖框架和基础设施
- 通过接口反转依赖

**Event Sourcing** — 适合需要完整审计轨迹、时间旅行的业务
- 存储事件而非当前状态
- 重放事件重建状态

**CQRS** — 适合读写模式差异大的场景
- 命令（写）和查询（读）分离
- 读模型可针对查询优化

**微服务/模块化单体** — 架构粒度选择
- 微服务：团队独立部署、技术栈异构
- 模块化单体：单进程但模块边界清晰，必要时可拆"""

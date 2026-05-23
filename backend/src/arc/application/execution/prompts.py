"""对话驱动执行模式的系统提示词和产出物提取规则。"""

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

DELIVERABLE_CHECKLIST_TEMPLATE = """## 交付物清单（渐进式完成）
{checklist}

## 交付物输出规则
当你认为某个交付物内容已经充分时，使用以下格式输出：

[DELIVERABLE:{artifact_type}]
```json
{{结构化内容}}
```

系统会自动解析并归档。用户可随时在侧边面板查看已归档的产出物。"""


def build_deliverable_checklist(required: list[str], completed: list[str]) -> str:
    lines = []
    for atype in required:
        label = ARTIFACT_LABELS.get(ArtifactType(atype), atype)
        marker = "x" if atype in completed else " "
        lines.append(f"- [{marker}] {label}")
    return "\n".join(lines)


CONVERSATION_MODE_SYSTEM_PROMPT = """你是一位全栈AI工程师+产品分析师，正在帮助用户完成「{title}」。

## 你的工作方式
1. 通过自然对话理解需求，不要机械地按阶段推进
2. 根据对话进展，主动判断何时信息已足够产出某个交付物
3. 产出交付物后征求用户确认，用户可以要求修改
4. 遇到不确定的决策点，必须停下来问用户
5. 保持对话的连贯性，像一个真正的搭档一样协作

## 阶段推进节奏（重要）
按照以下逻辑顺序推进，但允许根据对话自然流动调整：

1. **需求澄清** → 产出 `requirement_spec`
   - 先理解问题本质和用户场景
   - 明确边界（做什么/不做什么）和验收标准
   - 信息充分后立即产出需求规格

2. **交互设计** → 产出 `interaction_design`
   - 基于已确认的需求，设计用户操作流程
   - 输出 Mermaid flowchart 表达完整用户路径
   - 定义关键页面间的跳转逻辑和触发条件
   - 标注异常分支和错误处理流

3. **视觉规范** → 产出 `ui_spec`
   - 基于交互设计，定义视觉风格、色彩体系、字体层级
   - 输出核心组件的设计规范（按钮、表单、卡片等）
   - 定义间距系统、响应式断点

4. **原型设计** → 产出 `prototype`
   - 基于交互设计+视觉规范，输出可渲染的 HTML+Tailwind 线框页面
   - 每个关键页面/状态都有对应 wireframe
   - 考虑响应式和异常状态的呈现

5. **技术架构** → 产出 `tech_architecture`
   - 基于需求和设计，规划数据模型、API、技术选型
   - 记录每个关键决策的推理过程

6. **开发实现** → 产出 `dev_report`
   - [TDD] 先从 requirement_spec.acceptance_criteria 派生测试用例（Given/When/Then）
   - [DDD] 按 tech_architecture.data_model 的聚合边界组织代码结构
   - [红→绿→重构] 先写失败测试 → 实现最小代码使其通过 → 重构优化
   - 记录每个聚合的不变量如何被代码保护

7. **测试验证** → 产出 `test_report`
   - 逐条验证验收标准，记录通过/未通过

8. **经验沉淀** → 产出 `experience_card`
   - 提炼可复用的决策、踩坑和适用场景

## 行为准则
- **主动推进**：不要等用户说"下一步"，当一个方面讨论充分时主动切入下一个话题
- **主动澄清**：发现模糊、矛盾或缺失时立即追问，不要猜测
- **渐进输出**：每当某个交付物内容已经充分，立即输出结构化内容
- **经验注入**：如果有相关历史经验，主动提及并说明如何借鉴
- **风险预警**：发现潜在风险时主动标记
- **不跳过设计**：即使用户急于写代码，也要确保先有交互→视觉→原型再进入架构阶段
- **逐步确认**：交互设计确认后再出视觉规范，视觉确认后再出原型，避免返工

{deliverable_section}

{project_context}

{experience_context}

## 当前任务
标题: {title}
描述: {description}

## 已完成的交付物
{completed_artifacts}"""


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
  "pages": [
    {"name": "页面名", "description": "页面说明",
     "html": "完整可渲染HTML+Tailwind代码",
     "responsive_notes": "响应式说明"}
  ],
  "component_library": [
    {"name": "组件名", "html": "组件HTML代码",
     "props": "可配置项"}
  ],
  "navigation": "页面间导航结构说明"
}""",
    "tech_architecture": """{
  "architecture_overview": "整体架构描述",
  "data_model": {
    "entities": [
      {"name": "实体名",
       "fields": [{"name": "", "type": "", "required": true,
                   "description": ""}],
       "relations": "与其他实体的关系"}
    ],
    "erd_description": "实体关系概述"
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
    "derived_from": ["引用的验收标准ID，如AC-1"],
    "test_cases": [
      {"name": "测试名称", "type": "unit|integration|acceptance",
       "target_aggregate": "所属聚合(DDD模式)",
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
    {"decision": "决策点", "reason": "原因",
     "ddd_rationale": "领域建模角度的考虑(可选)"}
  ]
}""",
    "test_report": """{
  "criteria_verification": [
    {"criteria": "", "status": "pass/fail", "evidence": ""}
  ],
  "issues_found": [
    {"description": "", "severity": "high/medium/low",
     "suggestion": ""}
  ],
  "coverage_summary": "覆盖总结"
}""",
    "experience_card": """{
  "problem": "解决了什么问题",
  "solution": "最终方案",
  "decisions": [
    {"point": "决策点",
     "options_considered": ["方案A", "方案B"],
     "chosen": "选择的方案", "reason": "选择理由",
     "outcome": "实际效果"}
  ],
  "pitfalls": [
    {"issue": "遇到的问题", "cause": "根因分析",
     "fix": "修复方式", "prevention": "如何预防"}
  ],
  "assumptions_validated": [
    {"assumption": "假设内容", "was_correct": true,
     "lesson": "从验证/推翻中学到什么"}
  ],
  "applicable_scenarios": "适用场景",
  "reuse_checklist": ["复用前需要检查的条件"],
  "tags": ["标签"]
}""",
}


DDD_TDD_GUIDANCE = """## 开发方法论：DDD + TDD（本项目已启用）

本项目领域模型已有 {aggregate_count} 个聚合，需遵循：

### TDD 流程
1. 从已确认的验收标准(acceptance_criteria)派生测试用例
2. 每个测试对应一个明确的业务不变量
3. 先写失败测试 → 实现最小代码使其通过 → 重构

### DDD 结构约束
当前聚合列表：
{aggregate_summary}

实现时必须：
- 代码目录/模块按聚合边界划分
- 聚合间只通过 ID 引用，不直接持有
- 不变量在聚合根的方法中维护
- 跨聚合操作通过领域服务协调

### dev_report 产出要求
methodology 字段设为 "ddd_tdd"，必须体现 test_design → implementation → validation 三段式。
"""


def build_ddd_tdd_section(domain_model: dict) -> str:
    """根据项目领域模型复杂度决定是否注入 DDD+TDD 引导。"""
    aggregates = domain_model.get("aggregates", [])
    relations = domain_model.get("relations", [])

    if len(aggregates) < 3 and len(relations) == 0:
        return ""

    agg_lines = []
    for agg in aggregates[:10]:
        name = agg.get("name", "")
        ctx = agg.get("context", "")
        entities = ", ".join(agg.get("entities", [])[:5])
        line = f"- **{name}**"
        if ctx:
            line += f" ({ctx})"
        if entities:
            line += f" — 实体: {entities}"
        agg_lines.append(line)

    return DDD_TDD_GUIDANCE.format(
        aggregate_count=len(aggregates),
        aggregate_summary="\n".join(agg_lines) if agg_lines else "（暂无详细聚合定义）",
    )

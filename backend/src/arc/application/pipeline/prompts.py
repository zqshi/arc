"""Pipeline 阶段提示词和交付物定义。

设计哲学：
  - System prompt: 只给意图 + 上下文，不给步骤/规则
  - Extraction prompt: 输出接口契约（JSON schema），让代码能解析
  - Gate evaluation: 后置质量验证，不达标则反馈给 Agent 补充
  - 质量保障靠"产出 → 验证 → 反馈"循环，不靠前置规则约束
"""

from __future__ import annotations

from arc.domain.pipeline.value_objects import PhaseType

# ---------------------------------------------------------------------------
# 需求澄清层级（供 Agent 参考，不是强制步骤）
# ---------------------------------------------------------------------------

SOCRATIC_LAYERS = [
    {
        "layer": 1, "name": "问题定义",
        "focus": "理解问题本质、根因和影响面",
        "questions": [
            "这个需求要解决什么具体问题？根因是什么？",
            "谁是受影响的用户？目前的替代方案是什么？",
            "不解决会怎样？影响的频率和严重程度？",
        ],
    },
    {
        "layer": 2, "name": "用户场景",
        "focus": "具象化使用场景、交互流程",
        "questions": [
            "典型使用场景——用户从哪进入，做什么操作，期望什么结果？",
            "有哪些边缘场景或异常路径？",
        ],
    },
    {
        "layer": 3, "name": "约束条件",
        "focus": "明确边界、限制和隐含假设",
        "questions": [
            "明确不做什么？为什么？",
            "技术约束和业务约束各有哪些？",
        ],
    },
    {
        "layer": 4, "name": "成功标准",
        "focus": "定义可验证的完成条件",
        "questions": [
            "做到什么程度算完成？有可量化的指标吗？",
            "如果只能做一件事，哪个验收条件绝不能妥协？",
        ],
    },
    {
        "layer": 5, "name": "风险预判",
        "focus": "提前识别风险和应对策略",
        "questions": [
            "最可能卡住的技术点在哪？",
            "主方案行不通时 Plan B 是什么？",
        ],
    },
    {
        "layer": 6, "name": "反诘",
        "focus": "挑战需求前提假设",
        "questions": [
            "我们在解决正确的问题吗？",
            "这个需求基于什么假设？假设被验证过吗？",
        ],
    },
]

# ---------------------------------------------------------------------------
# Phase system prompts — 意图驱动，只给目标和上下文
# ---------------------------------------------------------------------------

CLARIFICATION_SYSTEM_PROMPT = """\
帮用户把「{title}」的需求从模糊想法澄清为可执行的需求规格。

当前追问方向：**{layer_name}**（{layer_focus}）
参考问题：
{layer_questions}

已收集信息：
{collected_info}"""

INPUT_SUFFICIENCY_PROMPT = """\
评估以下需求信息是否足够开始深度分析。

需求标题：{title}
需求描述：{description}
对话内容：{conversation_summary}

输出 JSON:
```json
{{
  "sufficient": true/false,
  "target_users": {{"status": "clear/vague/missing", "evidence": ""}},
  "core_problem": {{"status": "clear/vague/missing", "evidence": ""}},
  "feature_direction": {{"status": "clear/vague/missing", "evidence": ""}},
  "follow_up_questions": ["（仅 sufficient=false 时）"]
}}
```"""

UI_DESIGN_SYSTEM_PROMPT = """\
基于已确认的需求规格，设计交互方案。

需求规格：
{requirement_spec}"""

ARCHITECTURE_SYSTEM_PROMPT = """\
基于需求和设计，产出技术实现方案。

需求规格：
{requirement_spec}

交互设计：
{ui_design}"""

DEVELOPMENT_SYSTEM_PROMPT = """\
协助完成开发实现。

需求：{requirement_spec}
架构方案：{tech_architecture}"""

TESTING_SYSTEM_PROMPT = """\
验证开发成果是否满足需求。

验收标准：
{acceptance_criteria}

开发报告：
{dev_report}"""

DEPLOYMENT_SYSTEM_PROMPT = """\
协助部署已通过测试的代码。"""

EXTRACTION_SYSTEM_PROMPT = """\
从已完成的项目中提取可复用的经验。

全生命周期数据：
{full_context}"""

# ---------------------------------------------------------------------------
# Extraction prompts — 输出接口契约（JSON schema）
# ---------------------------------------------------------------------------

CLARIFICATION_EXTRACTION_PROMPT = """\
根据对话内容提取结构化需求规格。输出 JSON:

```json
{{
  "background": "需求背景",
  "target_users": [
    {{"type": "用户类型", "traits": "特征", "core_need": "诉求"}}
  ],
  "core_value": {{
    "user_value": "", "business_value": "", "tech_value": ""
  }},
  "user_stories": [
    {{"role": "", "goal": "", "benefit": "",
     "priority": "P0/P1/P2", "acceptance": ""}}
  ],
  "user_scenarios": "",
  "boundaries": {{
    "in_scope": [], "out_of_scope": [], "constraints": []
  }},
  "acceptance_criteria": [
    {{"id": "AC-1", "scenario": "", "steps": "",
     "expected": "", "priority": "P0/P1/P2"}}
  ],
  "risk_assessment": [
    {{"risk": "", "probability": "高/中/低",
     "impact": "高/中/低", "mitigation": ""}}
  ],
  "assumptions": [
    {{"assumption": "", "confidence": "高/中/低",
     "validation_method": ""}}
  ]
}}
```"""

UI_DESIGN_EXTRACTION_PROMPT = """\
根据对话提取交互设计方案。输出 JSON:

```json
{{
  "flow_diagram": "Mermaid flowchart 代码",
  "wireframes": [
    {{"page_name": "", "description": "",
     "html": "HTML+Tailwind 线框代码"}}
  ],
  "component_specs": [
    {{"name": "", "purpose": "", "behavior": "", "states": ""}}
  ],
  "interaction_rules": "",
  "responsive_notes": ""
}}
```"""

ARCHITECTURE_EXTRACTION_PROMPT = """\
根据对话提取技术架构方案。输出 JSON:

```json
{{
  "architecture_overview": "",
  "domain_design": {{
    "subdomains": [{{"name": "", "type": "", "description": ""}}],
    "bounded_contexts": [{{"name": "", "subdomain": "", "description": ""}}],
    "context_relations": [{{"from": "", "to": "", "type": "", "description": ""}}]
  }},
  "data_model": {{
    "entities": [
      {{"name": "", "fields": [{{"name": "", "type": "", "required": true, "description": ""}}],
       "relations": "", "bounded_context": ""}}
    ],
    "erd_description": ""
  }},
  "event_storming": {{
    "events": [{{"name": "", "context": "", "trigger": "", "actor": "", "aggregate": ""}}],
    "commands": [{{"name": "", "actor": "", "target_aggregate": "", "events_produced": []}}]
  }},
  "api_design": [
    {{"method": "", "path": "", "description": "",
     "request_params": [], "response_example": ""}}
  ],
  "tech_decisions": [
    {{"decision": "", "options_considered": [],
     "chosen": "", "reason": "", "trade_offs": ""}}
  ],
  "implementation_plan": [
    {{"step": "", "description": "", "estimated_effort": "", "priority": ""}}
  ],
  "non_functional": {{
    "performance": "", "security": "", "scalability": ""
  }}
}}
```"""

DEVELOPMENT_EXTRACTION_PROMPT = """\
根据开发过程提取结构化报告。输出 JSON:

```json
{{
  "execution_log": "",
  "code_changes": [],
  "test_results": "",
  "decisions_made": [{{"decision": "", "reason": ""}}]
}}
```"""

TESTING_EXTRACTION_PROMPT = """\
根据测试过程提取报告。输出 JSON:

```json
{{
  "criteria_verification": [
    {{"criteria": "", "status": "pass/fail", "evidence": ""}}
  ],
  "issues_found": [
    {{"description": "", "severity": "high/medium/low", "suggestion": ""}}
  ],
  "coverage_summary": ""
}}
```"""

DEPLOYMENT_EXTRACTION_PROMPT = """\
根据部署过程提取报告。输出 JSON:

```json
{{
  "deploy_log": "",
  "service_url": "",
  "health_check_result": "",
  "rollback_plan": ""
}}
```"""

EXTRACTION_EXTRACTION_PROMPT = """\
提取结构化经验卡片。输出 JSON:

```json
{{
  "problem": "",
  "solution": "",
  "decisions": [
    {{"point": "", "options_considered": [],
     "chosen": "", "reason": "", "outcome": ""}}
  ],
  "pitfalls": [
    {{"issue": "", "cause": "", "fix": "", "prevention": ""}}
  ],
  "assumptions_validated": [
    {{"assumption": "", "was_correct": true, "lesson": ""}}
  ],
  "applicable_scenarios": "",
  "reuse_checklist": [],
  "tags": []
}}
```"""

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PHASE_SYSTEM_PROMPTS: dict[PhaseType, str] = {
    PhaseType.CLARIFICATION: CLARIFICATION_SYSTEM_PROMPT,
    PhaseType.UI_DESIGN: UI_DESIGN_SYSTEM_PROMPT,
    PhaseType.ARCHITECTURE: ARCHITECTURE_SYSTEM_PROMPT,
    PhaseType.DEVELOPMENT: DEVELOPMENT_SYSTEM_PROMPT,
    PhaseType.TESTING: TESTING_SYSTEM_PROMPT,
    PhaseType.DEPLOYMENT: DEPLOYMENT_SYSTEM_PROMPT,
    PhaseType.EXTRACTION: EXTRACTION_SYSTEM_PROMPT,
}

PHASE_EXTRACTION_PROMPTS: dict[PhaseType, str] = {
    PhaseType.CLARIFICATION: CLARIFICATION_EXTRACTION_PROMPT,
    PhaseType.UI_DESIGN: UI_DESIGN_EXTRACTION_PROMPT,
    PhaseType.ARCHITECTURE: ARCHITECTURE_EXTRACTION_PROMPT,
    PhaseType.DEVELOPMENT: DEVELOPMENT_EXTRACTION_PROMPT,
    PhaseType.TESTING: TESTING_EXTRACTION_PROMPT,
    PhaseType.DEPLOYMENT: DEPLOYMENT_EXTRACTION_PROMPT,
    PhaseType.EXTRACTION: EXTRACTION_EXTRACTION_PROMPT,
}

PHASE_GREETINGS: dict[PhaseType, str] = {
    PhaseType.CLARIFICATION: "你好！我来帮你梳理「{title}」。先聊聊——这个需求主要想解决什么问题？",
    PhaseType.UI_DESIGN: "需求明确了，来设计交互方案。核心操作路径是什么？",
    PhaseType.ARCHITECTURE: "交互方案确认，来设计技术架构。你倾向什么技术栈？有什么约束？",
    PhaseType.DEVELOPMENT: "架构确认，开始开发。先从哪个模块开始？",
    PhaseType.TESTING: "开发完成，开始验证。你希望重点验证哪些场景？",
    PhaseType.DEPLOYMENT: "测试通过，准备部署。目标环境是什么？",
    PhaseType.EXTRACTION: "项目完成！回顾一下——最关键的决策是什么？有什么坑值得记录？",
}

# ---------------------------------------------------------------------------
# 后置质量验证（代码层保障，不是 prompt 规则）
# ---------------------------------------------------------------------------

PHASE_REQUIRED_FIELDS: dict[PhaseType, list[str]] = {
    PhaseType.CLARIFICATION: ["background", "target_users", "user_scenarios", "boundaries", "acceptance_criteria"],
    PhaseType.UI_DESIGN: ["flow_diagram", "wireframes", "component_specs"],
    PhaseType.ARCHITECTURE: ["architecture_overview", "data_model", "api_design", "tech_decisions"],
    PhaseType.DEVELOPMENT: ["execution_log", "code_changes", "test_results"],
    PhaseType.TESTING: ["criteria_verification", "issues_found", "coverage_summary"],
    PhaseType.DEPLOYMENT: ["deploy_log", "health_check_result", "build_evidence"],
    PhaseType.EXTRACTION: ["problem", "solution", "decisions"],
}

PHASES_NO_SKIP: set[PhaseType] = {
    # 仅 ui_design 可跳过(原型/交互设计可由用户手动产出), 其余阶段不可跳
    PhaseType.CLARIFICATION,
    PhaseType.ARCHITECTURE,
    PhaseType.DEVELOPMENT,
    PhaseType.TESTING,
    PhaseType.DEPLOYMENT,
    PhaseType.EXTRACTION,
}

GATE_EVALUATION_PROMPT = """\
评估这个阶段的产出物质量是否足以推进。

阶段: {phase_label}
产出物:
```json
{artifact_content}
```
{conventions_section}

输出 JSON:
```json
{{
  "passed": true/false,
  "score": 1-10,
  "gaps": ["具体缺失或不足"],
  "suggestion": "一句话建议"
}}
```"""


def build_clarification_prompt(current_layer: int, collected_info: str) -> str:
    layer_idx = min(current_layer - 1, len(SOCRATIC_LAYERS) - 1)
    layer = SOCRATIC_LAYERS[layer_idx]
    questions_text = "\n".join(f"- {q}" for q in layer["questions"])
    return CLARIFICATION_SYSTEM_PROMPT.format(
        title="{title}",
        layer_name=layer["name"],
        layer_focus=layer["focus"],
        layer_questions=questions_text,
        collected_info=collected_info or "（暂无）",
    )

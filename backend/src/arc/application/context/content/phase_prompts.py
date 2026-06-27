"""phase_prompts 内容显性化 (B方案/T3) — 阶段 prompt 文本集中声明。

纯内容 (phase system/extraction prompt + phase inference prompt) 从 pipeline/prompts.py
+ context/prompt_builder.py 迁入此模块, 消费方 (prompt_registry / artifact.service /
prompt_builder) 改读本模块。编排逻辑 (prompt 组装 / format 调用) 保持原模块。

复用 v6.9 dict + .get(key, default) fallback 模式。
"""

from __future__ import annotations

from arc.domain.pipeline.value_objects import PhaseType

# ---------------------------------------------------------------------------
# Phase system prompts — 意图驱动, 只给目标和上下文 (迁自 pipeline/prompts.py)
# ---------------------------------------------------------------------------
CLARIFICATION_SYSTEM_PROMPT = """\
帮用户把「{title}」的需求从模糊想法澄清为可执行的需求规格。

当前追问方向：**{layer_name}**（{layer_focus}）
参考问题：
{layer_questions}

已收集信息：
{collected_info}"""

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
# Extraction prompts — 输出接口契约 JSON schema (迁自 pipeline/prompts.py)
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
# Registry — phase → prompt 映射 (迁自 pipeline/prompts.py)
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


# ---------------------------------------------------------------------------
# Phase inference prompt — 迁自 context/prompt_builder.py
# ---------------------------------------------------------------------------
_PHASE_INFERENCE_PROMPT = """\
根据已完成的交付物, 推断当前应聚焦的开发阶段。

已完成交付物: {completed}
标准流程预筛: {prefilter}

阶段序列(参考): clarification → ui_design → architecture → development → testing → deployment

输出 JSON 契约:
{{"phase": "当前阶段名"}}

若实际进度与预筛一致则返回预筛值; 若需推进或回退(如某阶段产出有问题需返工),\
返回调整后的阶段名(必须是上述阶段序列之一)。"""

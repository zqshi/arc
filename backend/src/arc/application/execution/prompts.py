"""对话驱动执行模式的系统提示词和产出物提取规则。"""

from __future__ import annotations

from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType

ARTIFACT_TYPE_MARKERS: dict[str, ArtifactType] = {
    "requirement_spec": ArtifactType.REQUIREMENT_SPEC,
    "ui_design": ArtifactType.UI_DESIGN,
    "tech_architecture": ArtifactType.TECH_ARCHITECTURE,
    "dev_report": ArtifactType.DEV_REPORT,
    "test_report": ArtifactType.TEST_REPORT,
    "deploy_report": ArtifactType.DEPLOY_REPORT,
    "experience_card": ArtifactType.EXPERIENCE_CARD,
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

## 行为准则
- **主动推进**：不要等用户说"下一步"，当一个方面讨论充分时主动切入下一个话题
- **主动澄清**：发现模糊、矛盾或缺失时立即追问，不要猜测
- **渐进输出**：每当某个交付物内容已经充分，立即输出结构化内容
- **经验注入**：如果有相关历史经验，主动提及并说明如何借鉴
- **风险预警**：发现潜在风险时主动标记

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
  "user_scenarios": "用户场景和交互流程",
  "goals": "目标和期望结果",
  "boundaries": "边界条件和约束",
  "acceptance_criteria": "验收标准（可量化）",
  "risk_assessment": "风险评估和应对"
}""",
    "ui_design": """{
  "flow_diagram": "Mermaid flowchart代码",
  "wireframes": [{"page_name": "", "description": "", "html": ""}],
  "component_specs": [{"name": "", "purpose": "", "behavior": "", "states": ""}],
  "interaction_rules": "交互规则",
  "responsive_notes": "响应式说明"
}""",
    "tech_architecture": """{
  "architecture_overview": "整体架构",
  "data_model": "数据模型",
  "api_design": "API设计",
  "tech_decisions": [{"decision": "", "options": "", "chosen": "", "reason": ""}],
  "implementation_plan": "实现步骤"
}""",
    "dev_report": """{
  "execution_log": "执行过程",
  "code_changes": ["变更列表"],
  "test_results": "测试结果",
  "decisions_made": [{"decision": "", "reason": ""}]
}""",
    "test_report": """{
  "criteria_verification": [{"criteria": "", "status": "pass/fail", "evidence": ""}],
  "issues_found": [{"description": "", "severity": "high/medium/low", "suggestion": ""}],
  "coverage_summary": "覆盖总结"
}""",
    "experience_card": """{
  "problem": "解决了什么问题",
  "solution": "最终方案",
  "decisions": [{"point": "", "chosen": "", "reason": ""}],
  "pitfalls": [{"issue": "", "cause": "", "fix": ""}],
  "applicable_scenarios": "适用场景",
  "tags": ["标签"]
}""",
}

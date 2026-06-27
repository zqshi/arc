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
    PhaseType.CLARIFICATION: [
        "background", "target_users", "user_scenarios",
        "boundaries", "acceptance_criteria",
    ],
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
{charter_section}
{conventions_section}
{capabilities_section}

输出 JSON:
```json
{{
  "passed": true/false,
  "score": 1-10,
  "gaps": ["具体缺失或不足"],
  "suggestion": "一句话建议"
}}
```"""

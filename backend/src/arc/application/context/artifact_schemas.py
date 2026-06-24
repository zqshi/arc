"""Artifact JSON schema 定义 (v5.8.0 从 prompts.py 拆分)。

每个 artifact_type 对应的结构化 JSON schema, 作为 Agent 输出契约。
纯数据, 独立可维护。
"""
from __future__ import annotations

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
    "app_code": """{
  "project_dir": "代码工程根目录相对路径, 如 'generated/my-app'",
  "tech_stack": ["react", "typescript", "vite"],
  "framework": "react|vue|svelte|vanilla",
  "build_command": "npm run build",
  "run_command": "npm run dev",
  "entry_points": ["src/main.tsx"],
  "has_backend": false,
  "backend_type": "none|embedded|external|supabase"
}""",
    "service_spec": """{
  "data_model_ref": "引用的领域模型版本, 如 'v3'",
  "data_persistence": "none|embedded|external|supabase",
  "endpoints": [
    {"method": "GET|POST|PUT|DELETE", "path": "/api/...",
     "description": "端点用途", "auth_required": true}
  ],
  "auth_strategy": "none|jwt|supabase_auth|external",
  "external_api_base": "data_persistence=external 时填写, 否则 null",
  "notes": "自由备注"
}""",
}

"""LLM 驱动的领域模型质量校验。"""

from __future__ import annotations

import json
import logging

from arc.application.ai.json_extract import extract_json
from arc.application.ai.llm_adapter import LLMMessage
from arc.application.ai.resilience import create_resilient_adapter

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """\
你是一位资深 DDD（领域驱动设计）架构师，拥有 15 年以上的领域建模经验。
请对以下领域模型进行专业的质量评审。

## 领域模型数据
{domain_model_json}

## 评审维度

### 战略设计评审
- 子域划分是否合理？核心域/支撑域/通用域的分类是否准确？
- 核心域是否聚焦（一般不超过 3 个）？
- 通用域是否有不必要的自研（如认证、支付、通知等应优先考虑外采）？
- 限界上下文边界是否清晰？职责是否单一？
- 上下文间的协作关系类型是否正确（ACL/OHS/SharedKernel/CustomerSupplier 等）？
- 是否存在循环依赖或双向耦合？

### 战术设计评审
- 聚合设计是否合理？每个聚合是否都有明确的事务一致性边界和不变量？
- 聚合大小是否适度？（超过 5 个实体的聚合通常需要拆分）
- 实体 vs 值对象的区分是否正确？（不可变的概念应建模为值对象）
- 聚合间是否通过 ID 引用而非直接持有？
- 是否有聚合缺少明确的聚合根？
- 领域事件的识别是否充分？是否覆盖了关键业务流程？
- 聚合的方法/命令是否体现了业务意图（非 CRUD 命名）？

### 整体评估
- 模型的完整度如何？是否有明显缺失的领域概念？
- 命名是否统一、清晰、符合通用语言（Ubiquitous Language）？
- 模型是否能支撑业务演进和扩展？
- 是否存在贫血模型的迹象（聚合只有数据没有行为）？

## 输出格式（严格 JSON）
{{
  "score": 0到100的质量分数,
  "level": "excellent 或 good 或 needs_improvement 或 poor",
  "issues": [
    {{"severity": "error 或 warning 或 info",
      "category": "strategic 或 tactical 或 naming 或 completeness",
      "title": "问题标题",
      "detail": "详细说明（含具体指向哪个子域/上下文/聚合）",
      "suggestion": "具体可操作的改进建议"}}
  ],
  "strengths": ["模型做得好的方面"],
  "summary": "一段话总结评审结论和最重要的改进方向"
}}

只输出 JSON，不要输出其他内容。"""


async def validate_domain_model(domain_model: dict) -> dict:
    """调用 LLM 对领域模型进行 DDD 专家级质量评审。"""
    if not domain_model or (
        not domain_model.get("aggregates")
        and not domain_model.get("subdomains")
    ):
        return {
            "score": 0,
            "level": "poor",
            "issues": [
                {
                    "severity": "error",
                    "category": "completeness",
                    "title": "领域模型为空",
                    "detail": "尚未建立任何领域模型数据",
                    "suggestion": "请先在对话中产出技术架构交付物，系统将自动提取领域模型",
                }
            ],
            "strengths": [],
            "summary": "领域模型为空，无法进行评审。",
        }

    adapter = create_resilient_adapter()
    try:
        prompt = VALIDATION_PROMPT.format(
            domain_model_json=json.dumps(domain_model, ensure_ascii=False, indent=2)
        )
        response = await adapter.chat(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.3,
            max_tokens=4096,
        )
        result = extract_json(response.content)
        if not isinstance(result, dict) or "score" not in result:
            logger.error("Domain model validation: unexpected LLM response format")
            return {
                "score": 0,
                "level": "poor",
                "issues": [],
                "strengths": [],
                "summary": "评审过程异常，请稍后重试。",
            }
        return result
    finally:
        await adapter.close()

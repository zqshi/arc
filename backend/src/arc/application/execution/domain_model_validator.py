"""LLM 驱动的领域模型质量校验。"""

from __future__ import annotations

import json
import logging

from arc.application.ai.json_extract import extract_json
from arc.application.ai.llm_adapter import LLMMessage
from arc.application.ai.resilience import create_resilient_adapter

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """\
评审以下领域模型的质量，给出评分和改进建议。

## 领域模型数据
{domain_model_json}

输出 JSON:
{{
  "score": 0-100,
  "level": "excellent|good|needs_improvement|poor",
  "issues": [
    {{"severity": "error|warning|info",
      "category": "strategic|tactical|naming|completeness",
      "title": "问题标题",
      "detail": "详细说明",
      "suggestion": "改进建议"}}
  ],
  "strengths": ["做得好的方面"],
  "summary": "总结"
}}

只输出 JSON。"""


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

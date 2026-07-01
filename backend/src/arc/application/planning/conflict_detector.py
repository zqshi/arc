"""领域模型冲突检测 — 基于聚合边界分析需求间的潜在冲突。

用途:
  - 版本规划阶段: 检测多个需求是否修改同一聚合 → 建议排序而非并行
  - 需求评审阶段: 识别跨聚合通信的高风险需求

设计原则:
  - 使用 LLM 推理而非硬编码规则 — 适应任何领域模型结构
  - 输出结构化 JSON, 供前端展示和规划 prompt 注入
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.infrastructure.repositories.project import ProjectRepository

logger = logging.getLogger(__name__)


CONFLICT_DETECTION_PROMPT = """\
分析以下功能需求列表，结合项目的领域模型，检测潜在的冲突和风险。

## 领域模型（当前架构）
{domain_model_section}

## 待规划需求
{features_section}

请分析：
1. 哪些需求会修改同一个聚合（写冲突 — 建议排序执行而非并行）
2. 哪些需求需要新增跨聚合通信（架构风险 — 复杂度高）
3. 哪些需求可能需要新增聚合或子域（架构扩展 — 需要提前设计）

输出 JSON:
```json
{{
  "conflicts": [
    {{
      "type": "write_conflict|cross_aggregate|new_aggregate",
      "severity": "high|medium|low",
      "features": ["需求A标题", "需求B标题"],
      "aggregate": "受影响的聚合名",
      "description": "冲突描述",
      "suggestion": "建议处理方式"
    }}
  ],
  "risk_summary": "整体风险评估（一句话）",
  "parallel_safe": ["可以安全并行的需求标题列表"],
  "sequential_required": [
    {{"first": "需求A", "then": "需求B", "reason": "原因"}}
  ]
}}
```

只输出 JSON。"""


class ConflictDetector:
    """基于领域模型检测需求间的架构冲突。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect(
        self,
        project_id: uuid.UUID,
        features: list[dict],
    ) -> dict:
        """检测需求列表中的潜在冲突。

        Args:
            project_id: 项目 ID（用于获取领域模型）
            features: 需求列表 [{"title": ..., "description": ...}, ...]

        Returns:
            冲突分析结果 dict
        """
        if not features or len(features) < 2:
            return {"conflicts": [], "risk_summary": "单个需求无冲突风险",
                    "parallel_safe": [f.get("title", "") for f in features],
                    "sequential_required": []}

        project_repo = ProjectRepository(self.db)
        project = await project_repo.get_by_id(project_id)
        if not project or not project.domain_model:
            return {"conflicts": [], "risk_summary": "无领域模型，无法检测冲突",
                    "parallel_safe": [f.get("title", "") for f in features],
                    "sequential_required": []}

        dm = project.domain_model
        domain_model_section = self._format_domain_model(dm)
        features_section = self._format_features(features)

        prompt = CONFLICT_DETECTION_PROMPT.format(
            domain_model_section=domain_model_section,
            features_section=features_section,
        )

        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.llm.service import LLMProviderService

        llm_config = await LLMProviderService(self.db).resolve_from_project(
            project, project.user_id
        )
        async with adapter_pool.acquire_for_project(llm_config) as adapter:
            response = await adapter.chat(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.2,
            )

        result = extract_json(response.content)
        if not isinstance(result, dict):
            logger.warning("Conflict detection JSON parse failed")
            return {"conflicts": [], "risk_summary": "分析失败",
                    "parallel_safe": [], "sequential_required": []}

        # 确保结构完整
        result.setdefault("conflicts", [])
        result.setdefault("risk_summary", "")
        result.setdefault("parallel_safe", [])
        result.setdefault("sequential_required", [])
        return result

    @staticmethod
    def _format_domain_model(dm: dict) -> str:
        """格式化领域模型供 prompt 使用。"""
        parts = []
        for sd in dm.get("subdomains", []):
            parts.append(f"- 子域: {sd.get('name')} ({sd.get('type', '')})")

        for agg in dm.get("aggregates", []):
            ctx = f" [{agg.get('context', '')}]" if agg.get("context") else ""
            entities = ", ".join(agg.get("entities", [])[:5])
            methods = ", ".join(agg.get("methods", [])[:5])
            parts.append(
                f"- 聚合: {agg.get('name')}{ctx}"
                + (f" | 实体: {entities}" if entities else "")
                + (f" | 方法: {methods}" if methods else "")
            )

        for rel in dm.get("aggregate_relations", dm.get("relations", []))[:10]:
            parts.append(
                f"- 关系: {rel.get('from')} → {rel.get('to')} [{rel.get('type', '')}]"
            )

        return "\n".join(parts) if parts else "（领域模型为空）"

    @staticmethod
    def _format_features(features: list[dict]) -> str:
        """格式化需求列表。"""
        parts = []
        for i, f in enumerate(features, 1):
            title = f.get("title", f"需求{i}")
            desc = f.get("description", "")
            complexity = f.get("complexity", "")
            line = f"{i}. {title}"
            if complexity:
                line += f" [{complexity}]"
            if desc:
                line += f"\n   {desc}"
            parts.append(line)
        return "\n".join(parts)

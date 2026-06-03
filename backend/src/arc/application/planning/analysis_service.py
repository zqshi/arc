"""版本迭代分析服务 — 从 planning_service.py 提取。

职责：
- AI 迭代分析生成 + fingerprint 缓存
- 结构化建议提取（action items）
- 项目级 LLM 配置接入
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 结构化输出约束 — 追加在分析 prompt 末尾
_STRUCTURED_SUFFIX = """

---

在分析末尾，请输出以下格式的 JSON 代码块，包含你的行动建议：

```json
{"suggestions": [{"priority": "P0", "action": "行动描述", "reason": "理由"}]}
```

优先级说明：P0=本迭代必做, P1=下迭代推荐, P2=后续考虑。
"""


class AnalysisService:
    """版本迭代分析服务。"""

    def __init__(self, db: "AsyncSession"):
        self.db = db

    async def analyze_iteration(
        self,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        *,
        llm_config: dict | None = None,
    ) -> tuple[str, bool, list[dict]]:
        """分析当前迭代状态。

        Returns:
            (content, cached, suggestions)
        """
        from arc.infrastructure.repositories.project import ProjectRepository, VersionRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        version_repo = VersionRepository(self.db)
        todo_repo = TodoRepository(self.db)
        project_repo = ProjectRepository(self.db)

        version = await version_repo.get_by_id(version_id)
        if not version:
            raise ValueError("版本不存在")

        todos, _ = await todo_repo.list_all(version_id=version_id, limit=1000)
        fingerprint = self._compute_fingerprint(todos)

        # 查缓存
        cached_result = await self._get_cached(version_id, fingerprint)
        if cached_result:
            content, suggestions = cached_result
            return content, True, suggestions

        # 生成新分析
        project = await project_repo.get_by_id(project_id)
        status_summary = self._format_todo_status(todos)

        project_context = ""
        if project:
            ctx_parts = []
            if project.tech_stack:
                ctx_parts.append(f"技术栈: {project.tech_stack}")
            if project.codebase_summary:
                ctx_parts.append(f"\n## 代码库概况\n{project.codebase_summary}")
            if project.conventions:
                ctx_parts.append(f"\n## 项目规范\n{project.conventions}")
            project_context = "\n".join(ctx_parts)

        from arc.application.planning.planning_service import ITERATION_REVIEW_PROMPT

        prompt = ITERATION_REVIEW_PROMPT.format(
            version_name=version.name,
            version_goal=version.goal,
            todo_status_summary=status_summary,
            project_context=project_context,
        ) + _STRUCTURED_SUFFIX

        # 使用项目级 LLM 或全局
        adapter = self._create_adapter(llm_config, project)
        try:
            from arc.application.ai.llm_adapter import LLMMessage
            response = await adapter.chat([LLMMessage(role="user", content=prompt)])
        finally:
            await adapter.close()

        content = response.content
        suggestions = self._extract_suggestions(content)

        # 持久化
        await self._persist(version_id, fingerprint, content, suggestions)

        return content, False, suggestions

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_adapter(self, llm_config: dict | None, project):
        """创建 LLM adapter — 优先项目配置，回退全局。"""
        # 先看传入的 llm_config
        if llm_config and llm_config.get("api_key"):
            from arc.application.ai.llm_adapter import create_llm_adapter_from_config
            from arc.application.ai.resilience import ResilientAdapter
            inner = create_llm_adapter_from_config(llm_config)
            return ResilientAdapter(inner)

        # 再看项目的 conversation_config.llm
        if project and project.conversation_config:
            project_llm = project.conversation_config.get("llm")
            if project_llm and project_llm.get("api_key"):
                from arc.application.ai.llm_adapter import create_llm_adapter_from_config
                from arc.application.ai.resilience import ResilientAdapter
                inner = create_llm_adapter_from_config(project_llm)
                return ResilientAdapter(inner)

        # 全局默认
        from arc.application.ai.resilience import create_resilient_adapter
        return create_resilient_adapter()

    async def _get_cached(self, version_id: uuid.UUID, fingerprint: str):
        """查询缓存。返回 (content, suggestions) 或 None。"""
        try:
            from sqlalchemy import select
            from arc.infrastructure.models.planning import VersionAnalysisModel

            result = await self.db.execute(
                select(VersionAnalysisModel)
                .where(
                    VersionAnalysisModel.version_id == version_id,
                    VersionAnalysisModel.fingerprint == fingerprint,
                )
                .order_by(VersionAnalysisModel.created_at.desc())
                .limit(1)
            )
            cached = result.scalar_one_or_none()
            if cached:
                suggestions = self._extract_suggestions(cached.content)
                return cached.content, suggestions
        except Exception:
            logger.debug("version_analyses table not available, skip cache")
            try:
                await self.db.rollback()
            except Exception:
                pass
        return None

    async def _persist(self, version_id: uuid.UUID, fingerprint: str, content: str, suggestions: list[dict]):
        """持久化分析结果。"""
        try:
            from arc.infrastructure.models.planning import VersionAnalysisModel
            analysis = VersionAnalysisModel(
                version_id=version_id,
                fingerprint=fingerprint,
                content=content,
            )
            self.db.add(analysis)
            await self.db.flush()
        except Exception:
            logger.debug("Failed to persist analysis, skipping")

    @staticmethod
    def _compute_fingerprint(todos) -> str:
        parts = sorted(f"{t.id}:{t.status.value}" for t in todos)
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def _extract_suggestions(content: str) -> list[dict]:
        """从分析 markdown 中提取 JSON 建议块。"""
        # 匹配 ```json ... ``` 中的 suggestions
        pattern = r'```json\s*(\{[^`]*"suggestions"[^`]*\})\s*```'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
            return data.get("suggestions", [])
        except (json.JSONDecodeError, AttributeError):
            return []

    @staticmethod
    def _format_todo_status(todos) -> str:
        lines = []
        for t in todos:
            lines.append(f"- [{t.status.value}] {t.title}")
            if t.description:
                lines.append(f"  描述: {t.description[:100]}")
        return "\n".join(lines) if lines else "（无需求）"

"""上下文组装器 — 替代 PromptBuilder.build_system_prompt() 的字符串拼接。

职责:
- 收集所有 Provider 的 ContextSegment
- 按 priority 排序
- 在阶段感知的 token 预算内组装
- 输出最终 system prompt 字符串
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.controller import estimate_tokens
from arc.application.context.protocol import (
    ContextRequest,
    ContextSegment,
    get_source_budget,
)

logger = logging.getLogger(__name__)

# 总 system prompt token 上限（P0 不受限，其他来源受各自 budget 限制）
MAX_SYSTEM_PROMPT_TOKENS = 20_000


class ContextAssembler:
    """按优先级和 token 预算组装上下文。

    使用方式:
        assembler = ContextAssembler(db)
        system_prompt = await assembler.assemble(request)
    """

    def __init__(self, db: AsyncSession):
        self._db = db
        self._providers = self._create_default_providers(db)
        # 经验 provider 的引用，用于获取注入的经验 ID
        self._experience_provider = None
        for p in self._providers:
            if p.source == "experience":
                self._experience_provider = p
                break

    @property
    def injected_experience_ids(self) -> list:
        """返回最近一次 assemble 注入的经验 ID。"""
        if self._experience_provider and hasattr(
            self._experience_provider, "injected_experience_ids"
        ):
            return self._experience_provider.injected_experience_ids
        return []

    @staticmethod
    def _create_default_providers(db: AsyncSession) -> list:
        """创建默认 provider 列表（注册顺序不影响结果，按 priority 排序）。"""
        from arc.application.context.providers import (
            CodeCapabilityProvider,
            DeliverableProvider,
            DomainModelProvider,
            ExperienceProvider,
            MethodologyProvider,
            ProjectInfoProvider,
            ReviewFeedbackProvider,
            SufficiencyHintProvider,
        )

        return [
            DeliverableProvider(db),        # P0: 核心指令
            ProjectInfoProvider(db),        # P1: 项目信息
            DomainModelProvider(db),        # P1: 领域模型
            ReviewFeedbackProvider(db),     # P1: 评审反馈
            ExperienceProvider(db),         # P1: 经验召回
            CodeCapabilityProvider(db),     # P1: 代码能力
            MethodologyProvider(db),        # P2: 方法论
            SufficiencyHintProvider(),      # P2: 充分性提示
        ]

    def register(self, provider) -> None:
        """注册额外的 Provider。"""
        self._providers.append(provider)

    async def assemble(self, request: ContextRequest) -> str:
        """收集所有 Provider 的片段，按优先级和 budget 组装。

        Returns:
            组装好的 system prompt 字符串。
        """
        from arc.application.context.prompts import (
            AUTOPILOT_SECTION,
            CONVERSATION_MODE_SYSTEM_PROMPT,
        )

        # 1. 收集所有 segments
        all_segments: list[ContextSegment] = []
        for provider in self._providers:
            try:
                segments = await provider.provide(request)
                all_segments.extend(segments)
            except Exception:
                logger.warning(
                    "Provider %s failed, skipping",
                    getattr(provider, "source", type(provider).__name__),
                    exc_info=True,
                )

        # 2. 按 priority 排序（0 最高，3 最低）
        all_segments.sort(key=lambda s: s.priority)

        # 3. 按 budget 裁剪
        assembled_parts: dict[str, str] = {}
        total_tokens = 0

        for seg in all_segments:
            source_budget = get_source_budget(request.phase, seg.source)

            # P0 不受 budget 限制
            if seg.priority == 0:
                key = f"{seg.source}_{id(seg)}"
                assembled_parts[key] = seg.content
                total_tokens += seg.token_estimate
                continue

            # 检查来源 budget
            existing_tokens = sum(
                s.token_estimate for s in all_segments
                if s.source == seg.source and id(s) in {
                    id(s2) for key, s2 in []
                }
            )
            if seg.token_estimate > source_budget:
                # 截断到 budget
                from arc.application.context.controller import _truncate_to_tokens
                seg.content = _truncate_to_tokens(seg.content, source_budget)
                seg.token_estimate = source_budget

            if total_tokens + seg.token_estimate > MAX_SYSTEM_PROMPT_TOKENS:
                logger.info(
                    "System prompt budget exhausted (%d/%d), dropping %s (P%d)",
                    total_tokens, MAX_SYSTEM_PROMPT_TOKENS,
                    seg.source, seg.priority,
                )
                continue

            key = f"{seg.source}_{id(seg)}"
            assembled_parts[key] = seg.content
            total_tokens += seg.token_estimate

        # 4. 组装分类内容
        deliverable_section = ""
        project_context = ""
        methodology_section = ""
        experience_context = ""
        sufficiency_hint = ""
        completed_artifacts = ""

        for key, content in assembled_parts.items():
            source = key.split("_")[0]
            if source == "deliverable":
                if "交付物清单" in content:
                    deliverable_section = content
                elif "已完成" in content:
                    completed_artifacts = content.replace("## 已完成的交付物\n", "")
            elif source in ("project", "domain", "review", "code"):
                project_context += ("\n\n" + content if project_context else content)
            elif source == "methodology":
                methodology_section = content
            elif source == "experience":
                experience_context = content
            elif source == "sufficiency":
                sufficiency_hint = content

        # 5. 检查 autopilot
        autonomy = await self._get_autonomy(request)
        if autonomy == "full":
            project_context += "\n\n" + AUTOPILOT_SECTION

        # 6. 填充模板
        todo = request.todo
        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            methodology_section=methodology_section,
            project_context=project_context,
            experience_context=experience_context,
            sufficiency_hint=sufficiency_hint,
            completed_artifacts=completed_artifacts or "暂无",
        )

    async def _get_autonomy(self, request: ContextRequest) -> str:
        if not request.todo or not request.todo.project_id:
            return "supervised"
        from arc.infrastructure.repositories.project import ProjectRepository
        project = await ProjectRepository(self._db).get_by_id(
            request.todo.project_id
        )
        if not project or not project.conversation_config:
            return "supervised"
        return project.conversation_config.get("agent_autonomy", "supervised")

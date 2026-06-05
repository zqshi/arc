"""经验反馈闭环 — 从 execution_engine.py 提取。

职责：
- todo 完成时自动提取经验
- 精细化更新被复用经验的反馈（区分"AI 引用" vs "仅注入"）
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arc.application.context.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


async def extract_and_feedback(
    db: AsyncSession,
    todo_id: uuid.UUID,
    prompt_builder: PromptBuilder,
) -> None:
    """todo 完成时：提取经验 + 更新复用反馈。

    从 ExecutionEngine._extract_experience 提取为独立函数，
    便于在 autopilot 和 generate_response_stream 两处调用。
    """
    from arc.application.experience.service import ExperienceService
    from arc.infrastructure.repositories.todo import TodoRepository

    try:
        todo_repo = TodoRepository(db)
        todo = await todo_repo.get_by_id(todo_id)
        if not todo:
            return
        svc = ExperienceService(db)
        await svc.extract_from_todo(todo)

        await _update_reused_experiences(db, todo_id, prompt_builder)
    except Exception as exc:
        logger.warning(
            "Experience extraction failed for todo %s: %s", todo_id, exc
        )


async def _update_reused_experiences(
    db: AsyncSession,
    todo_id: uuid.UUID,
    prompt_builder: PromptBuilder,
) -> None:
    """精细化经验反馈 — 区分"被 AI 引用"和"仅注入但未使用"。

    反馈策略：
    - AI response 中出现经验关键词（title/problem 的前 30 字） → helpful=True
    - 注入但未被 AI 引用 → 中性（不改变 confidence）
    - 用户手动标记走独立 API（不在此处处理）
    """
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.infrastructure.repositories.experience import ExperienceRepository

    try:
        conv_repo = ConversationRepository(db)
        exp_repo = ExperienceRepository(db)

        conversations = await conv_repo.list_by_todo_id(todo_id)

        # 1. 收集所有注入的经验 ID
        injected_ids: set[str] = set()
        for conv in conversations:
            for msg in conv.messages:
                if msg.metadata and "referenced_experiences" in msg.metadata:
                    for ref in msg.metadata["referenced_experiences"]:
                        if isinstance(ref, dict) and "id" in ref:
                            injected_ids.add(ref["id"])
                        elif isinstance(ref, str):
                            injected_ids.add(ref)

        if prompt_builder.injected_experience_ids:
            for eid in prompt_builder.injected_experience_ids:
                injected_ids.add(str(eid))

        if not injected_ids:
            return

        # 2. 收集所有 AI assistant 回复的文本
        ai_text = ""
        for conv in conversations:
            for msg in conv.messages:
                if msg.role.value == "assistant":
                    ai_text += msg.content + "\n"

        # 3. 逐个检查经验是否被"引用"（AI 输出中出现经验关键内容）
        import uuid as _uuid
        actually_used: list[str] = []
        merely_injected: list[str] = []

        for eid_str in injected_ids:
            try:
                eid = _uuid.UUID(eid_str)
                exp = await exp_repo.get_by_id(eid)
                if not exp:
                    continue

                keywords = []
                if exp.title:
                    keywords.append(exp.title[:30])
                if exp.problem:
                    keywords.append(exp.problem[:30])

                was_referenced = any(kw in ai_text for kw in keywords if len(kw) >= 5)

                if was_referenced:
                    exp.apply_feedback(helpful=True)
                    await exp_repo.update(exp)
                    actually_used.append(eid_str)
                else:
                    merely_injected.append(eid_str)

            except (ValueError, Exception) as exc:
                logger.debug("Skip reuse update for %s: %s", eid_str, exc)

        if actually_used or merely_injected:
            logger.info(
                "Experience feedback for todo %s: %d actually_used, %d merely_injected",
                todo_id, len(actually_used), len(merely_injected),
            )
    except Exception as exc:
        logger.warning(
            "Reused experience update failed for todo %s: %s", todo_id, exc
        )

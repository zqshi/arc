"""Checkpoint & Handoff Protocol — Harness §11.

长程执行的状态快照和跨 session 恢复。
检查点存储在 conversation 的 system message metadata 中（利用 JSONB），
无需新增数据库表。

HandoffPackage 是结构化的会话状态摘要，用于：
1. 跨 session 恢复 — 新会话通过 receive_handoff 重建上下文
2. 里程碑状态记录 — 每完成一个关键步骤创建 checkpoint
3. 错误回退 — rollback 到最近正确的 checkpoint
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arc.domain.conversation.entity import Message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HandoffPackage:
    """结构化的会话状态摘要。"""

    goal: str
    completed: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    failed_attempts: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "completed": self.completed,
            "pending": self.pending,
            "key_decisions": self.key_decisions,
            "failed_attempts": self.failed_attempts,
            "modified_files": self.modified_files,
            "created_at": self.created_at,
        }

    def to_prompt(self) -> str:
        """转换为可注入 system prompt 的文本。"""
        parts = [f"## 会话继承摘要\n\n**目标**: {self.goal}"]

        if self.completed:
            parts.append("### 已完成\n" + "\n".join(f"- {c}" for c in self.completed))
        if self.pending:
            parts.append("### 待办\n" + "\n".join(f"- {p}" for p in self.pending))
        if self.key_decisions:
            parts.append("### 关键决策\n" + "\n".join(f"- {d}" for d in self.key_decisions))
        if self.failed_attempts:
            parts.append(
                "### 失败记录（不要重复这些方法）\n"
                + "\n".join(f"- {f}" for f in self.failed_attempts)
            )
        if self.modified_files:
            parts.append("### 已修改文件\n" + "\n".join(f"- `{f}`" for f in self.modified_files))

        return "\n\n".join(parts)


class CheckpointManager:
    """检查点管理器。"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_checkpoint(
        self,
        conversation_id: uuid.UUID,
        state: dict,
        label: str = "",
    ) -> str:
        """创建检查点，存储为 conversation 的 system message。

        Returns:
            checkpoint_id
        """
        from arc.domain.conversation.entity import Conversation
        from arc.domain.todo.value_objects import MessageRole
        from arc.infrastructure.repositories.conversation import ConversationRepository

        repo = ConversationRepository(self._db)
        conv = await repo.get_by_id(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        checkpoint_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        msg = conv.add_message(
            role=MessageRole.SYSTEM,
            content=f"[Checkpoint: {label or checkpoint_id}]",
            metadata={
                "checkpoint": True,
                "checkpoint_id": checkpoint_id,
                "checkpoint_label": label,
                "checkpoint_state": state,
                "checkpoint_created_at": now,
            },
        )
        await repo.add_message(conversation_id, msg)

        logger.info(
            "Checkpoint created: %s for conversation %s",
            checkpoint_id, conversation_id,
        )
        return checkpoint_id

    async def restore_checkpoint(
        self,
        conversation_id: uuid.UUID,
        checkpoint_id: str,
    ) -> dict | None:
        """恢复指定检查点的状态。"""
        from arc.infrastructure.repositories.conversation import ConversationRepository

        repo = ConversationRepository(self._db)
        conv = await repo.get_by_id(conversation_id)
        if not conv:
            return None

        for msg in reversed(conv.messages):
            if (
                msg.metadata
                and msg.metadata.get("checkpoint")
                and msg.metadata.get("checkpoint_id") == checkpoint_id
            ):
                return msg.metadata.get("checkpoint_state", {})

        logger.warning(
            "Checkpoint %s not found in conversation %s",
            checkpoint_id, conversation_id,
        )
        return None

    async def create_handoff_package(
        self,
        conversation_id: uuid.UUID,
        goal: str,
    ) -> HandoffPackage:
        """从对话历史中提取结构化的 HandoffPackage。"""
        from arc.infrastructure.repositories.conversation import ConversationRepository

        repo = ConversationRepository(self._db)
        conv = await repo.get_by_id(conversation_id)
        if not conv:
            return HandoffPackage(goal=goal)

        messages = conv.messages
        completed = _extract_patterns(messages, _COMPLETED_PATTERNS)
        pending = _extract_patterns(messages, _PENDING_PATTERNS)
        decisions = _extract_patterns(messages, _DECISION_PATTERNS)
        failures = _extract_patterns(messages, _FAILURE_PATTERNS)
        files = _extract_file_paths(messages)

        return HandoffPackage(
            goal=goal,
            completed=completed[:20],
            pending=pending[:10],
            key_decisions=decisions[:10],
            failed_attempts=failures[:10],
            modified_files=files[:20],
            created_at=datetime.now(timezone.utc).isoformat(),
        )


# ------------------------------------------------------------------
# Pattern extraction helpers
# ------------------------------------------------------------------

_COMPLETED_PATTERNS = ["已完成", "完成了", "done", "✅", "已实现", "已修复"]
_PENDING_PATTERNS = ["还需要", "待办", "TODO", "接下来", "下一步", "还没"]
_DECISION_PATTERNS = ["决定", "选择了", "采用", "方案是", "决策"]
_FAILURE_PATTERNS = ["失败", "错误", "不行", "放弃了", "failed", "error", "不可行"]


def _extract_patterns(
    messages: list[Message], patterns: list[str],
) -> list[str]:
    """从消息中提取匹配特定模式的句子。"""
    results: list[str] = []
    seen: set[str] = set()

    for msg in messages:
        if msg.role.value != "assistant":
            continue
        for line in msg.content.split("\n"):
            line = line.strip()
            if not line or len(line) < 5:
                continue
            for pattern in patterns:
                if pattern in line and line not in seen:
                    # 截取有意义的片段
                    snippet = line[:200] if len(line) > 200 else line
                    results.append(snippet)
                    seen.add(line)
                    break

    return results


def _extract_file_paths(messages: list[Message]) -> list[str]:
    """从消息中提取被修改的文件路径。"""
    import re

    file_re = re.compile(r"(?:write_file|修改了|创建了|wrote)\s*[:\s]*[`\"']?([^\s`\"']+\.\w+)")
    paths: list[str] = []
    seen: set[str] = set()

    for msg in messages:
        for match in file_re.finditer(msg.content):
            fpath = match.group(1)
            if fpath not in seen:
                paths.append(fpath)
                seen.add(fpath)

    return paths

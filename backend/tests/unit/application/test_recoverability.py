"""单元测试 — v5.6.0 可恢复性模块。

覆盖:
- A2: Autopilot 断点恢复
- C4: Orchestration 可观测性输出格式
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCheckpointRestore:
    """验证 CheckpointManager.restore_from_checkpoint 行为。"""

    def _patch_conv_repo(self, conv):
        """创建 ConversationRepository mock，用于内部 deferred import。"""
        mock_repo_cls = MagicMock()
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=conv)
        return patch(
            "arc.infrastructure.repositories.conversation.ConversationRepository",
            mock_repo_cls,
        ), mock_repo_cls

    @pytest.mark.asyncio
    async def test_restore_returns_none_when_no_checkpoint(self):
        from arc.application.execution.checkpoint import CheckpointManager

        db = AsyncMock()
        mgr = CheckpointManager(db)

        conv_id = uuid.uuid4()
        conv = MagicMock()
        conv.messages = [
            MagicMock(metadata=None, role=MagicMock(value="user"), content="hello"),
            MagicMock(metadata={}, role=MagicMock(value="assistant"), content="hi"),
        ]

        # Directly inject the mock by replacing the deferred import target
        mock_repo_cls = MagicMock()
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=conv)

        import arc.infrastructure.repositories.conversation as conv_mod
        original = conv_mod.ConversationRepository
        conv_mod.ConversationRepository = mock_repo_cls
        try:
            result = await mgr.restore_from_checkpoint(conv_id)
        finally:
            conv_mod.ConversationRepository = original

        assert result is None

    @pytest.mark.asyncio
    async def test_restore_builds_handoff_from_checkpoint(self):
        from arc.application.execution.checkpoint import CheckpointManager

        db = AsyncMock()
        mgr = CheckpointManager(db)

        conv_id = uuid.uuid4()
        conv = MagicMock()
        conv.messages = [
            MagicMock(
                metadata=None,
                role=MagicMock(value="user"),
                content="实现登录功能",
            ),
            MagicMock(
                metadata={
                    "checkpoint": True,
                    "checkpoint_id": "abc123",
                    "checkpoint_label": "autopilot-round-3",
                    "checkpoint_state": {
                        "round": 3,
                        "completed": ["需求分析", "技术方案"],
                        "completion_pct": 60,
                    },
                    "checkpoint_created_at": "2026-06-05T10:00:00Z",
                },
                role=MagicMock(value="system"),
                content="[Checkpoint: autopilot-round-3]",
            ),
        ]

        mock_repo_cls = MagicMock()
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=conv)

        import arc.infrastructure.repositories.conversation as conv_mod
        original = conv_mod.ConversationRepository
        conv_mod.ConversationRepository = mock_repo_cls
        try:
            result = await mgr.restore_from_checkpoint(conv_id)
        finally:
            conv_mod.ConversationRepository = original

        assert result is not None
        assert "实现登录功能" in result.goal
        assert "需求分析" in result.completed
        assert "技术方案" in result.completed
        assert "round 4" in result.pending[0]

    @pytest.mark.asyncio
    async def test_get_resume_round(self):
        from arc.application.execution.checkpoint import CheckpointManager

        db = AsyncMock()
        mgr = CheckpointManager(db)

        conv_id = uuid.uuid4()
        conv = MagicMock()
        conv.messages = [
            MagicMock(metadata={"checkpoint": True, "checkpoint_state": {"round": 5}}),
        ]

        mock_repo_cls = MagicMock()
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=conv)

        import arc.infrastructure.repositories.conversation as conv_mod
        original = conv_mod.ConversationRepository
        conv_mod.ConversationRepository = mock_repo_cls
        try:
            round_num = await mgr.get_resume_round(conv_id)
        finally:
            conv_mod.ConversationRepository = original

        assert round_num == 5

    @pytest.mark.asyncio
    async def test_get_resume_round_no_checkpoint(self):
        from arc.application.execution.checkpoint import CheckpointManager

        db = AsyncMock()
        mgr = CheckpointManager(db)

        conv = MagicMock()
        conv.messages = [MagicMock(metadata={})]

        mock_repo_cls = MagicMock()
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=conv)

        import arc.infrastructure.repositories.conversation as conv_mod
        original = conv_mod.ConversationRepository
        conv_mod.ConversationRepository = mock_repo_cls
        try:
            round_num = await mgr.get_resume_round(uuid.uuid4())
        finally:
            conv_mod.ConversationRepository = original

        assert round_num == 0

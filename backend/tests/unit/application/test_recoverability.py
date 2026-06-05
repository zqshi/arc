"""单元测试 — v5.6.0 可恢复性模块。

覆盖:
- A2: Autopilot 断点恢复
- C2: SSE Event Buffer
- C4: Orchestration 可观测性输出格式
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =====================================================================
# C2: SSE Event Buffer
# =====================================================================


class TestSSEEventBuffer:
    """验证 event buffer 的核心行为。"""

    def test_append_returns_incremental_ids(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=100)
        id1 = buf.append({"event": "a"})
        id2 = buf.append({"event": "b"})
        id3 = buf.append({"event": "c"})

        assert id1 == "1"
        assert id2 == "2"
        assert id3 == "3"
        assert buf.size == 3

    def test_replay_from_returns_events_after_id(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=100)
        buf.append({"event": "a"})
        buf.append({"event": "b"})
        buf.append({"event": "c"})

        missed = buf.replay_from("1")
        assert len(missed) == 2
        assert missed[0]["event"] == "b"
        assert missed[1]["event"] == "c"

    def test_replay_from_empty_id_returns_all(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=100)
        buf.append({"event": "a"})
        buf.append({"event": "b"})

        missed = buf.replay_from("")
        assert len(missed) == 2

    def test_replay_from_latest_returns_empty(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=100)
        buf.append({"event": "a"})
        buf.append({"event": "b"})

        missed = buf.replay_from("2")
        assert missed == []

    def test_ring_buffer_evicts_oldest(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=3)
        buf.append({"event": "a"})  # id=1
        buf.append({"event": "b"})  # id=2
        buf.append({"event": "c"})  # id=3
        buf.append({"event": "d"})  # id=4, evicts "a"

        assert buf.size == 3
        # Replaying from 0 should give b,c,d (a is gone)
        all_events = buf.replay_from("0")
        assert len(all_events) == 3
        assert all_events[0]["event"] == "b"
        assert all_events[2]["event"] == "d"

    def test_replay_from_evicted_id_returns_entire_buffer(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer(max_size=2)
        buf.append({"event": "a"})  # id=1
        buf.append({"event": "b"})  # id=2
        buf.append({"event": "c"})  # id=3, evicts "a"

        # Client had id=1 which is evicted — return everything available
        missed = buf.replay_from("1")
        assert len(missed) == 2
        assert missed[0]["event"] == "b"
        assert missed[1]["event"] == "c"

    def test_latest_event_id(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer()
        assert buf.latest_event_id is None

        buf.append({"event": "x"})
        assert buf.latest_event_id == "1"

    def test_clear_resets_state(self):
        from arc.interface.ws.event_buffer import SSEEventBuffer

        buf = SSEEventBuffer()
        buf.append({"event": "x"})
        buf.clear()

        assert buf.size == 0
        assert buf.latest_event_id is None


class TestSSEEventBufferRegistry:
    """验证 registry 管理多个 conversation buffer。"""

    def test_get_or_create(self):
        from arc.interface.ws.event_buffer import SSEEventBufferRegistry

        reg = SSEEventBufferRegistry()
        buf1 = reg.get_or_create("conv-1")
        buf2 = reg.get_or_create("conv-1")

        assert buf1 is buf2  # same instance
        assert reg.active_count == 1

    def test_different_conversations_isolated(self):
        from arc.interface.ws.event_buffer import SSEEventBufferRegistry

        reg = SSEEventBufferRegistry()
        buf1 = reg.get_or_create("conv-1")
        buf2 = reg.get_or_create("conv-2")

        buf1.append({"event": "a"})
        assert buf2.size == 0
        assert reg.active_count == 2

    def test_cleanup_removes_stale_buffers(self):
        import time
        from arc.interface.ws.event_buffer import SSEEventBufferRegistry

        reg = SSEEventBufferRegistry()
        buf = reg.get_or_create("conv-1")
        buf.append({"event": "a"})
        # Manually backdate last_access
        buf._last_access = time.monotonic() - 600  # 10 min ago

        removed = reg.cleanup(ttl_seconds=300)
        assert removed == 1
        assert reg.active_count == 0

    def test_remove(self):
        from arc.interface.ws.event_buffer import SSEEventBufferRegistry

        reg = SSEEventBufferRegistry()
        reg.get_or_create("conv-1")
        reg.remove("conv-1")
        assert reg.active_count == 0
        assert reg.get("conv-1") is None


# =====================================================================
# A2: Checkpoint Restore
# =====================================================================


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

        import arc.application.execution.checkpoint as ckpt_mod
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

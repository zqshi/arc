"""StreamManager 单元测试。"""

from __future__ import annotations

import asyncio
import time

from arc.application.execution.stream_manager import (
    _RETENTION_SECONDS,
    StreamManager,
    StreamSession,
)


class TestStreamSession:
    def test_initial_state(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        assert session.conversation_id == "conv-1"
        assert session.done is False
        assert session.error is None
        assert session.events == []
        assert session.full_content == ""

    def test_publish_appends_event(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.publish({"content": "hello"})
        assert len(session.events) == 1
        assert session.full_content == "hello"

    def test_publish_accumulates_content(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.publish({"content": "hello "})
        session.publish({"content": "world"})
        assert session.full_content == "hello world"

    def test_publish_ignores_error_type_content(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.publish({"type": "error", "content": "oops"})
        assert session.full_content == ""

    def test_finish_marks_done(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.finish()
        assert session.done is True
        assert session.error is None

    def test_finish_with_error(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.finish(error="something broke")
        assert session.done is True
        assert session.error == "something broke"

    def test_is_expired_false_when_active(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        assert session.is_expired is False

    def test_is_expired_false_immediately_after_finish(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        session.finish()
        assert session.is_expired is False  # within retention

    def test_subscriber_receives_events(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.publish({"content": "test"})
        assert not q.empty()
        event = q.get_nowait()
        assert event["content"] == "test"

    def test_remove_subscriber(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.remove_subscriber(q)
        session.publish({"content": "after remove"})
        assert q.empty()

    def test_finish_sends_sentinel_to_subscribers(self) -> None:
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.finish()
        event = q.get_nowait()
        assert event.get("_sentinel") is True


class TestStreamManager:
    def test_get_session_returns_none_initially(self) -> None:
        mgr = StreamManager()
        assert mgr.get_session("nonexistent") is None

    async def test_start_stream_creates_session(self) -> None:
        mgr = StreamManager()

        async def dummy_stream():
            yield {"content": "hello"}

        session = mgr.start_stream("conv-1", dummy_stream())
        assert session is not None
        assert session.conversation_id == "conv-1"
        assert mgr.get_session("conv-1") is session

        # Wait for completion
        await asyncio.sleep(0.1)

    async def test_start_stream_reuses_active_session(self) -> None:
        mgr = StreamManager()

        async def slow_stream():
            await asyncio.sleep(10)
            yield {"content": "done"}

        session1 = mgr.start_stream("conv-1", slow_stream())
        session2 = mgr.start_stream("conv-1", slow_stream())
        assert session1 is session2

        # Clean up
        if session1.task:
            session1.task.cancel()

    async def test_subscribe_replays_and_gets_live(self) -> None:
        mgr = StreamManager()
        collected = []

        async def gen():
            yield {"content": "chunk1"}
            yield {"content": "chunk2"}

        session = mgr.start_stream("conv-1", gen())

        # Wait for stream to finish
        await asyncio.sleep(0.1)

        async for event in mgr.subscribe(session):
            collected.append(event)

        assert len(collected) == 2
        assert collected[0]["content"] == "chunk1"
        assert collected[1]["content"] == "chunk2"

    def test_cleanup_expired_removes_old_sessions(self) -> None:
        mgr = StreamManager()
        session = StreamSession(conversation_id="conv-old")
        session.finish()
        # Manually set finished time in the past
        session._finished_at = time.monotonic() - _RETENTION_SECONDS - 10
        mgr._active["conv-old"] = session

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.get_session("conv-old") is None

    def test_cleanup_keeps_active_sessions(self) -> None:
        mgr = StreamManager()
        session = StreamSession(conversation_id="conv-active")
        mgr._active["conv-active"] = session

        removed = mgr.cleanup_expired()
        assert removed == 0
        assert mgr.get_session("conv-active") is session

    async def test_stream_error_is_captured(self) -> None:
        mgr = StreamManager()
        error_captured = []

        async def failing_stream():
            yield {"content": "start"}
            raise RuntimeError("boom")

        async def on_error(session, exc):
            error_captured.append(str(exc))

        session = mgr.start_stream("conv-err", failing_stream(), on_error=on_error)
        await asyncio.sleep(0.2)

        assert session.done is True
        assert session.error == "boom"
        assert "boom" in error_captured

    async def test_stream_complete_callback(self) -> None:
        mgr = StreamManager()
        completed = []

        async def simple_stream():
            yield {"content": "data"}

        async def on_complete(session):
            completed.append(session.conversation_id)

        session = mgr.start_stream("conv-ok", simple_stream(), on_complete=on_complete)
        await asyncio.sleep(0.1)

        assert session.done is True
        assert "conv-ok" in completed

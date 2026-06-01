"""StreamManager 单元测试 — 验证流式生成与 WS 解耦机制。"""

import asyncio
import uuid

import pytest

from arc.application.execution.stream_manager import StreamManager, StreamSession


# ---------------------------------------------------------------------------
# StreamSession 单元测试
# ---------------------------------------------------------------------------

class TestStreamSession:
    def test_publish_appends_to_events(self):
        session = StreamSession(conversation_id="conv-1")
        session.publish({"type": "chunk", "content": "hello"})
        assert len(session.events) == 1
        assert session.events[0]["content"] == "hello"

    def test_publish_accumulates_content(self):
        session = StreamSession(conversation_id="conv-1")
        session.publish({"type": "chunk", "content": "hello "})
        session.publish({"type": "chunk", "content": "world"})
        assert session.full_content == "hello world"

    def test_publish_ignores_error_type_content(self):
        session = StreamSession(conversation_id="conv-1")
        session.publish({"type": "error", "detail": "fail", "content": "err"})
        assert session.full_content == ""

    def test_finish_sets_done(self):
        session = StreamSession(conversation_id="conv-1")
        assert not session.done
        session.finish()
        assert session.done

    def test_finish_with_error(self):
        session = StreamSession(conversation_id="conv-1")
        session.finish(error="boom")
        assert session.done
        assert session.error == "boom"

    def test_subscriber_receives_events(self):
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.publish({"type": "chunk", "content": "hi"})
        assert not q.empty()
        event = q.get_nowait()
        assert event["content"] == "hi"

    def test_remove_subscriber(self):
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.remove_subscriber(q)
        session.publish({"type": "chunk", "content": "hi"})
        assert q.empty()

    def test_finish_sends_sentinel(self):
        session = StreamSession(conversation_id="conv-1")
        q = session.add_subscriber()
        session.finish()
        event = q.get_nowait()
        assert event.get("_sentinel") is True

    def test_is_expired_when_fresh(self):
        session = StreamSession(conversation_id="conv-1")
        assert not session.is_expired

    def test_is_expired_when_not_done(self):
        session = StreamSession(conversation_id="conv-1")
        session.done = False
        assert not session.is_expired


# ---------------------------------------------------------------------------
# StreamManager 单元测试
# ---------------------------------------------------------------------------

class TestStreamManager:
    def test_get_session_returns_none_initially(self):
        mgr = StreamManager()
        assert mgr.get_session("unknown") is None

    @pytest.mark.asyncio
    async def test_start_stream_creates_session(self):
        mgr = StreamManager()

        async def gen():
            yield {"type": "stream_chunk", "content": "hello"}

        session = mgr.start_stream("conv-1", gen())
        assert session is not None
        assert not session.done
        # Wait for task to finish
        await session.task
        assert session.done
        assert session.full_content == "hello"

    @pytest.mark.asyncio
    async def test_subscribe_replays_and_streams(self):
        mgr = StreamManager()

        async def gen():
            yield {"type": "stream_chunk", "message_id": "m1", "content": "a"}
            yield {"type": "stream_chunk", "message_id": "m1", "content": "b"}
            yield {"type": "stream_end", "message_id": "m1"}

        session = mgr.start_stream("conv-1", gen())
        # Wait for completion so all events are in the buffer
        await session.task

        events = []
        async for event in mgr.subscribe(session):
            events.append(event)

        # Should have all 3 events via replay
        assert len(events) == 3
        assert events[0]["content"] == "a"
        assert events[1]["content"] == "b"
        assert events[2]["type"] == "stream_end"

    @pytest.mark.asyncio
    async def test_subscribe_live_events(self):
        mgr = StreamManager()
        barrier = asyncio.Event()

        async def gen():
            yield {"type": "stream_chunk", "message_id": "m1", "content": "first"}
            barrier.set()
            await asyncio.sleep(0.05)
            yield {"type": "stream_chunk", "message_id": "m1", "content": "second"}

        session = mgr.start_stream("conv-1", gen())
        await barrier.wait()

        events = []
        async for event in mgr.subscribe(session):
            events.append(event)

        contents = [e.get("content", "") for e in events if e.get("content")]
        assert "first" in contents
        assert "second" in contents

    @pytest.mark.asyncio
    async def test_reuse_existing_session(self):
        mgr = StreamManager()
        barrier = asyncio.Event()

        async def gen():
            barrier.set()
            await asyncio.sleep(10)  # Long running
            yield {"type": "stream_chunk", "content": "late"}

        session1 = mgr.start_stream("conv-1", gen())
        await barrier.wait()

        # Starting again returns the same session
        async def gen2():
            yield {"type": "stream_chunk", "content": "other"}

        session2 = mgr.start_stream("conv-1", gen2())
        assert session2 is session1

        session1.task.cancel()
        try:
            await session1.task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_error_handling(self):
        mgr = StreamManager()

        async def gen():
            yield {"type": "stream_chunk", "content": "ok"}
            raise RuntimeError("boom")

        session = mgr.start_stream("conv-1", gen())
        await session.task

        assert session.done
        assert session.error is not None
        # Error event should be in the buffer
        error_events = [e for e in session.events if e.get("type") == "error"]
        assert len(error_events) == 1

    def test_cleanup_expired(self):
        import time
        mgr = StreamManager()
        session = StreamSession(conversation_id="conv-1")
        session.done = True
        session._finished_at = time.monotonic() - 120  # Expired
        mgr._active["conv-1"] = session

        removed = mgr.cleanup_expired()
        assert removed == 1
        assert mgr.get_session("conv-1") is None

    def test_message_id_generation(self):
        session = StreamSession(conversation_id="conv-1")
        # message_id should be a valid UUID string
        uuid.UUID(session.message_id)

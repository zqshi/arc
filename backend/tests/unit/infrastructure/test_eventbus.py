"""Tests for infrastructure/eventbus — 跨进程事件总线抽象 (v6.7)。

EventBus 是 stream_manager / connection_manager / project_task_stream /
scan_manager 共享的抽象: 把"进程内 asyncio.Queue 投递"抽象为可替换后端
(InMemory 单进程 / Redis 跨进程)。本测试验证 InMemoryEventBus 的契约,
RedisEventBus 的测试见 test_eventbus_redis.py。

契约:
- publish(channel, event): 投递事件到该 channel 的所有订阅者
- subscribe(channel): 返回 async iterator, 先重放已缓冲事件再实时投递
- publish 在无订阅者时缓冲 (供迟到的订阅者 replay)
- shutdown: 通知所有订阅者终止
"""

from __future__ import annotations

import asyncio

import pytest

from arc.infrastructure.eventbus import InMemoryEventBus


class TestPublishSubscribe:
    """核心投递语义。"""

    @pytest.mark.asyncio
    async def test_subscriber_receives_published_event(self):
        """订阅后, publish 的事件被实时收到。"""
        bus = InMemoryEventBus()
        received: list[dict] = []

        async def consume():
            async for event in bus.subscribe("ch1"):
                received.append(event)
                break  # 收到一条即退出

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # 让订阅者就位
        await bus.publish("ch1", {"type": "chunk", "content": "hi"})
        await asyncio.wait_for(consumer, timeout=1.0)

        assert received == [{"type": "chunk", "content": "hi"}]
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_all_receive(self):
        """同一 channel 的多个订阅者都收到 (广播, 非队列竞争)。"""
        bus = InMemoryEventBus()
        a: list[dict] = []
        b: list[dict] = []

        async def consume(buf):
            async for event in bus.subscribe("ch1"):
                buf.append(event)
                break

        t1 = asyncio.create_task(consume(a))
        t2 = asyncio.create_task(consume(b))
        await asyncio.sleep(0.05)
        await bus.publish("ch1", {"x": 1})
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)

        assert a == [{"x": 1}]
        assert b == [{"x": 1}]
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_publish_buffers_when_no_subscriber(self):
        """无订阅者时, 事件被缓冲 (供迟到订阅者 replay)。"""
        bus = InMemoryEventBus()
        await bus.publish("ch1", {"seq": 1})
        await bus.publish("ch1", {"seq": 2})

        received: list[dict] = []

        async def consume():
            async for event in bus.subscribe("ch1"):
                received.append(event)
                if len(received) >= 2:
                    break

        consumer = asyncio.create_task(consume())
        await asyncio.wait_for(consumer, timeout=1.0)

        # 迟到订阅者应重放缓冲的 2 条
        assert [e["seq"] for e in received] == [1, 2]
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_replay_then_live(self):
        """订阅先重放历史, 再接收实时事件。"""
        bus = InMemoryEventBus()
        await bus.publish("ch1", {"seq": 1})  # 历史
        await asyncio.sleep(0.01)

        received: list[dict] = []

        async def consume():
            async for event in bus.subscribe("ch1"):
                received.append(event)
                if len(received) >= 3:
                    break

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)  # 让 replay 完成
        await bus.publish("ch1", {"seq": 2})  # 实时
        await bus.publish("ch1", {"seq": 3})  # 实时
        await asyncio.wait_for(consumer, timeout=1.0)

        assert [e["seq"] for e in received] == [1, 2, 3]
        await bus.shutdown()


class TestShutdown:
    """优雅终止订阅。"""

    @pytest.mark.asyncio
    async def test_shutdown_terminates_subscribers(self):
        """shutdown 让所有订阅者的 async iterator 正常结束。"""
        bus = InMemoryEventBus()
        finished = asyncio.Event()

        async def consume():
            async for _ in bus.subscribe("ch1"):
                pass
            finished.set()

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.05)
        await bus.shutdown()
        await asyncio.wait_for(finished.wait(), timeout=1.0)
        assert finished.is_set()
        consumer.cancel()

    @pytest.mark.asyncio
    async def test_publish_after_shutdown_is_noop(self):
        """shutdown 后再 publish 不抛异常 (安全空操作)。"""
        bus = InMemoryEventBus()
        await bus.shutdown()
        await bus.publish("ch1", {"x": 1})  # 不应抛


class TestIsolation:
    """channel 间隔离。"""

    @pytest.mark.asyncio
    async def test_different_channels_isolated(self):
        """ch1 的事件不被 ch2 订阅者收到。"""
        bus = InMemoryEventBus()
        a: list[dict] = []
        b: list[dict] = []

        async def consume(ch, buf):
            async for event in bus.subscribe(ch):
                buf.append(event)
                break

        t1 = asyncio.create_task(consume("ch1", a))
        t2 = asyncio.create_task(consume("ch2", b))
        await asyncio.sleep(0.05)
        await bus.publish("ch1", {"to": "ch1"})
        await asyncio.wait_for(t1, timeout=1.0)
        t2.cancel()
        await bus.shutdown()

        assert a == [{"to": "ch1"}]
        assert b == []

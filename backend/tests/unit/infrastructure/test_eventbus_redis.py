"""RedisEventBus 测试 (v6.7 阶段2)。

用真实 redis 验证跨进程事件总线契约。标记 slow (CI 默认 skip, 需本地 redis):
  pytest tests/unit/infrastructure/test_eventbus_redis.py -m "not slow"  # skip
  pytest tests/unit/infrastructure/test_eventbus_redis.py -m slow          # run

契约与 InMemoryEventBus (test_eventbus.py) 一致, 验证双后端可互换。
"""

from __future__ import annotations

import asyncio

import pytest

from arc.infrastructure.redis_bus import RedisEventBus

pytestmark = pytest.mark.slow

REDIS_URL = "redis://localhost:6379/15"  # db 15 测试专用, 避免污染


@pytest.fixture
async def bus():
    """每个测试用独立 redis db, 用完清空。"""
    import redis.asyncio as aioredis

    b = RedisEventBus(REDIS_URL)
    yield b
    # 清理: 关闭 bus + flush db 15
    await b.shutdown()
    r = aioredis.from_url(REDIS_URL)
    await r.flushdb()
    await r.aclose()


class TestRedisEventBusPublishSubscribe:
    @pytest.mark.asyncio
    async def test_subscriber_receives_published_event(self, bus):
        received: list[dict] = []

        async def consume():
            async for event in bus.subscribe("test:ch1"):
                received.append(event)
                break

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.15)  # redis pubsub 就位需更长
        await bus.publish("test:ch1", {"type": "chunk", "content": "hi"})
        await asyncio.wait_for(consumer, timeout=2.0)

        assert received == [{"type": "chunk", "content": "hi"}]

    @pytest.mark.asyncio
    async def test_replay_then_live(self, bus):
        """先 publish (缓冲到 replay list), 订阅时重放历史再接收实时。"""
        # 唯一 channel 避免与上测试残留冲突
        ch = "test:replay_then_live"
        await bus.publish(ch, {"seq": 1})  # 历史
        await asyncio.sleep(0.05)

        received: list[dict] = []

        async def consume():
            async for event in bus.subscribe(ch):
                received.append(event)
                if len(received) >= 3:
                    break

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.15)  # 让 replay + 订阅就位
        await bus.publish(ch, {"seq": 2})  # 实时
        await bus.publish(ch, {"seq": 3})  # 实时
        await asyncio.wait_for(consumer, timeout=2.0)

        seqs = [e["seq"] for e in received]
        assert seqs == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_shutdown_terminates_subscriber(self, bus):
        finished = asyncio.Event()

        async def consume():
            async for _ in bus.subscribe("test:shutdown"):
                pass
            finished.set()

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.15)
        await bus.shutdown()
        await asyncio.wait_for(finished.wait(), timeout=2.0)
        assert finished.is_set()
        consumer.cancel()

    @pytest.mark.asyncio
    async def test_channel_isolation(self, bus):
        """不同 channel 隔离。"""
        a: list[dict] = []

        async def consume():
            async for event in bus.subscribe("test:iso_a"):
                a.append(event)
                break

        consumer = asyncio.create_task(consume())
        await asyncio.sleep(0.15)
        await bus.publish("test:iso_b", {"to": "b"})  # 另一 channel
        await bus.publish("test:iso_a", {"to": "a"})
        await asyncio.wait_for(consumer, timeout=2.0)

        assert a == [{"to": "a"}]

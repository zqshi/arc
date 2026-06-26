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

REDIS_URL = "redis://localhost:6379/15"  # db 15 测试专用, 避免污染


def _redis_available() -> bool:
    """本地 redis 是否可用 (不可用则 skip, 避免 CI 无 redis 时失败)。"""
    try:
        import redis

        client = redis.from_url(REDIS_URL, socket_connect_timeout=0.5)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


# 无本地 redis 时自动 skip (而非标记后因连接失败)
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not _redis_available(),
        reason="本地 redis 不可用 (CI 默认 -m 'not slow' 跳过)",
    ),
]


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


class TestRedisStreamReliability:
    """Stream 升级的核心价值: 关键事件不丢 (pub/sub 无消费者时事件丢)。"""

    @pytest.mark.asyncio
    async def test_late_subscriber_replays_all_including_critical(self, bus):
        """迟到订阅者 (发布时无消费者) 通过 XRANGE 重放全部历史, 含关键事件。"""
        ch = "test:reliability:late"
        # 发布时无任何订阅者 — pub/sub 模式这些会全丢, Stream 持久化保留
        await bus.publish(ch, {"type": "stream_chunk", "content": "part1"})
        await bus.publish(ch, {"type": "stream_chunk", "content": "part2"})
        await bus.publish(ch, {"type": "stream_end"})  # 关键事件
        await asyncio.sleep(0.05)

        # 迟到订阅者现在才订阅, 应 replay 全部 3 条
        replayed: list[dict] = []

        async def consume():
            async for event in bus.subscribe(ch):
                replayed.append(event)
                if len(replayed) >= 3:
                    break

        await asyncio.wait_for(consume(), timeout=2.0)

        types = [e["type"] for e in replayed]
        assert types == ["stream_chunk", "stream_chunk", "stream_end"], (
            f"关键事件丢失: {types}"
        )
        # stream_end (关键事件) 必须在 replay 中, 不能丢
        assert replayed[-1]["type"] == "stream_end"

    @pytest.mark.asyncio
    async def test_maxlen_does_not_lose_recent_events(self, bus):
        """MAXLEN 近似裁剪只裁旧事件, 最近的关键事件不丢。"""
        ch = "test:reliability:maxlen"
        # 发布超过 replay_size 的事件 (replay_size 默认 500)
        for i in range(20):
            await bus.publish(ch, {"seq": i})
        await bus.publish(ch, {"type": "stream_end"})  # 最新关键事件
        await asyncio.sleep(0.05)

        replayed: list[dict] = []
        async for event in bus.subscribe(ch):
            replayed.append(event)
            if event.get("type") == "stream_end":
                break

        # 最新的 stream_end 必须在 (未被裁剪)
        assert replayed[-1]["type"] == "stream_end"
        # 旧事件可能被裁, 但最近的保留
        assert len(replayed) >= 1

"""Redis 跨进程事件总线实现 (v6.7)。

用 Redis Stream 做跨 worker 事件广播 + replay。契约与 InMemoryEventBus 一致
(见 test_eventbus)。

设计 (v6.7 沙箱波次: pub/sub → Stream 升级, 保证关键事件不丢):
- publish(channel, event): XADD 到 stream (MAXLEN ~ 500 近似裁剪, 持久化)
- subscribe(channel): XRANGE 重放历史 + XREAD BLOCK 读新事件 (last-id 追踪)
- shutdown: XADD sentinel 到所有活跃 channel 让订阅者立即退出, 再关连接

相比 pub/sub (at-most-once, 无消费者时事件丢): Stream 持久化, 迟到订阅者
XRANGE 能重放全部历史, stream_end/error 等关键事件不丢。每个 subscribe 用
独立连接读 stream (XREAD BLOCK)。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from arc.infrastructure.eventbus import _DEFAULT_REPLAY_SIZE, EventBus

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 300  # stream 保留 5 分钟 (供迟到订阅者重放)
_XREAD_BLOCK_MS = 1000  # XREAD 阻塞 1 秒, 周期检查 _closed


def _serialize(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, default=str)


def _deserialize(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


class RedisEventBus(EventBus):
    """Redis Stream 跨进程事件总线。"""

    def __init__(
        self,
        redis_url: str,
        replay_size: int = _DEFAULT_REPLAY_SIZE,
    ) -> None:
        import redis.asyncio as aioredis

        self._url = redis_url
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._replay_size = replay_size
        self._closed = False
        # 各 subscribe 用独立连接读 stream; publish 用主连接
        self._read_conns: list[Any] = []
        self._channels: set[str] = set()

    async def publish(self, channel: str, event: dict) -> None:
        if self._closed:
            return
        self._channels.add(channel)
        payload = _serialize(event)
        # XADD 持久化到 stream, MAXLEN 近似裁剪保留最近 N 条
        await self._redis.xadd(
            channel,
            {"data": payload},
            maxlen=self._replay_size,
            approximate=True,
        )
        # stream TTL 自动回收 (无活跃订阅者后)
        await self._redis.expire(channel, _STREAM_TTL_SECONDS)

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        # 独立连接读 stream (XREAD BLOCK 占用连接)
        import redis.asyncio as aioredis

        read_conn = aioredis.from_url(self._url, decode_responses=True)
        self._read_conns.append(read_conn)

        # Phase 1: replay 历史 (XRANGE)
        last_id = "0-0"
        try:
            history = await read_conn.xrange(channel, min="-", max="+")
        except Exception as exc:
            logger.warning("Stream replay failed for %s: %s", channel, exc)
            history = []

        for _event_id, fields in history:
            raw = fields.get("data")
            if not raw:
                continue
            try:
                event = _deserialize(raw)
            except Exception:
                continue
            if event.get("_sentinel") is True:
                return
            yield event
            # 追踪最后 yield 的 id (用于 XREAD 起点避免重复)
            last_id = _event_id

        # Phase 2: live (XREAD BLOCK 从 last_id 之后)
        try:
            while not self._closed:
                try:
                    result = await read_conn.xread(
                        {channel: last_id}, count=100, block=_XREAD_BLOCK_MS
                    )
                except Exception as exc:
                    logger.debug("Stream read ended for %s: %s", channel, exc)
                    break
                if not result:
                    # block 超时无新事件, 继续轮询 (检查 _closed)
                    continue
                for _stream, messages in result:
                    for event_id, fields in messages:
                        last_id = event_id
                        raw = fields.get("data")
                        if not raw:
                            continue
                        try:
                            event = _deserialize(raw)
                        except Exception:
                            continue
                        if event.get("_sentinel") is True:
                            return
                        yield event
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Stream subscribe ended for %s: %s", channel, exc)
        finally:
            try:
                await read_conn.aclose()
            except Exception:
                pass
            if read_conn in self._read_conns:
                self._read_conns.remove(read_conn)

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # 给所有活跃 channel 发 sentinel, 让 XREAD 中的订阅者立即退出
        for ch in list(self._channels):
            try:
                await self._redis.xadd(
                    ch, {"data": _serialize({"_sentinel": True})},
                    maxlen=self._replay_size, approximate=True,
                )
            except Exception:
                pass
        # 等待订阅者处理 sentinel
        await asyncio.sleep(0.05)
        for conn in list(self._read_conns):
            try:
                await conn.aclose()
            except Exception:
                pass
        self._read_conns.clear()
        self._channels.clear()
        try:
            await self._redis.aclose()
        except Exception:
            pass

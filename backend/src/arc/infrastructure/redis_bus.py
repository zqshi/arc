"""Redis 跨进程事件总线实现 (v6.7 阶段2)。

用 redis.asyncio 的 pub/sub 做跨 worker 事件广播, 用 Redis List 做 replay
缓冲 (迟到订阅者重放历史)。契约与 InMemoryEventBus 一致 (见 test_eventbus)。

设计:
- publish(channel, event): PUBLISH 事件 + RPUSH 到 replay list (LTRIM + EXPIRE)
- subscribe(channel): 独立 pubsub 连接订阅 + 先 LRANGE 重放历史
- shutdown: 关闭所有 pubsub 与连接

每个 subscribe 用独立 pubsub (一个 redis 连接一个订阅者); replay list 与
channel 同生命周期, TTL 自动回收。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from arc.infrastructure.eventbus import _DEFAULT_REPLAY_SIZE, EventBus

logger = logging.getLogger(__name__)

_REPLAY_TTL_SECONDS = 300  # replay list 保留 5 分钟
_REPLAY_SUFFIX = ":events"  # replay list key 后缀


def _serialize(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False, default=str)


def _deserialize(raw: str | bytes) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)


class RedisEventBus(EventBus):
    """Redis pub/sub + List replay 跨进程事件总线。"""

    def __init__(
        self,
        redis_url: str,
        replay_size: int = _DEFAULT_REPLAY_SIZE,
    ) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._replay_size = replay_size
        self._closed = False
        # publish 用主连接, 各 subscribe 用独立 pubsub 连接
        self._pubsubs: list[Any] = []
        self._channels: set[str] = set()

    def _replay_key(self, channel: str) -> str:
        return f"{channel}{_REPLAY_SUFFIX}"

    async def publish(self, channel: str, event: dict) -> None:
        if self._closed:
            return
        self._channels.add(channel)
        # sentinel 不进 replay list (只通知 live 订阅者终止)
        is_sentinel = event.get("_sentinel") is True
        payload = _serialize(event)
        pipe = self._redis.pipeline()
        if not is_sentinel:
            pipe.rpush(self._replay_key(channel), payload)
            pipe.ltrim(self._replay_key(channel), -self._replay_size, -1)
            pipe.expire(self._replay_key(channel), _REPLAY_TTL_SECONDS)
        pipe.publish(channel, payload)
        await pipe.execute()

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        # 独立 pubsub 连接 (redis 限制: 一个连接一个订阅)
        pubsub = self._redis.pubsub()
        self._pubsubs.append(pubsub)
        await pubsub.subscribe(channel)

        # Phase 1: replay 历史 (从 replay list)
        try:
            history = await self._redis.lrange(
                self._replay_key(channel), 0, -1
            )
        except Exception as exc:
            logger.warning("Replay read failed for %s: %s", channel, exc)
            history = []

        for raw in history:
            try:
                yield _deserialize(raw)
            except Exception:
                continue

        # Phase 2: live (监听 pubsub)
        try:
            async for message in pubsub.listen():
                if self._closed:
                    break
                if message["type"] != "message":
                    continue
                try:
                    event = _deserialize(message["data"])
                except Exception:
                    continue
                if event.get("_sentinel") is True:
                    break
                yield event
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # shutdown 关闭连接 / 连接异常 → 正常结束迭代
            logger.debug("Redis pubsub listen ended for %s: %s", channel, exc)
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            except Exception:
                pass
            if pubsub in self._pubsubs:
                self._pubsubs.remove(pubsub)

    async def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        # 给所有活跃 channel 发 sentinel, 让 listen 中的订阅者自然退出
        for ch in list(self._channels):
            try:
                await self._redis.publish(ch, _serialize({"_sentinel": True}))
            except Exception:
                pass
        # 等待订阅者处理 sentinel 后关闭连接
        await asyncio.sleep(0.05)
        for pubsub in list(self._pubsubs):
            try:
                await pubsub.aclose()
            except Exception:
                pass
        self._pubsubs.clear()
        self._channels.clear()
        try:
            await self._redis.aclose()
        except Exception:
            pass

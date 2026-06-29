"""跨进程事件总线抽象 (v6.7)。

把 stream_manager / connection_manager / project_task_stream / scan_manager
共享的"进程内 asyncio.Queue 投递"抽象为可替换后端:

- InMemoryEventBus: 进程内 asyncio.Queue (单进程, 单 worker, 单测)
- RedisEventBus: Redis pub/sub + List replay (多 worker, 见阶段 2)

契约 (见 test_eventbus.py):
- publish(channel, event): 投递到所有订阅者, 同时写入 replay 缓冲
- subscribe(channel): async iterator, 先 replay 历史再接收实时事件
- shutdown: 通知所有订阅者终止迭代

设计: replay 缓冲按 channel 隔离 (deque maxlen), 迟到订阅者按序重放。
累积类业务状态 (full_content / accumulated summary) 不进 bus, 留在各
manager 自己维护 — bus 只负责事件投递。
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, AsyncIterator

from arc.infrastructure.eventbus_contract import _DEFAULT_REPLAY_SIZE, EventBus

logger = logging.getLogger(__name__)

# 订阅者队列上限 (背压保护, 超出丢弃事件并告警)
_SUBSCRIBER_QUEUE_MAX = 500

# 订阅终止哨兵
_SENTINEL: Any = object()


class InMemoryEventBus:
    """进程内事件总线 (单 worker / 单测默认后端)。

    每 channel 维护:
    - _replay[channel]: deque 缓冲最近事件 (供迟到订阅者)
    - _subs[channel]: 订阅者 asyncio.Queue 列表
    publish 同时写缓冲 + 投递所有 live 订阅者。
    """

    def __init__(self, replay_size: int = _DEFAULT_REPLAY_SIZE) -> None:
        self._replay: dict[str, deque[dict]] = {}
        self._subs: dict[str, list[asyncio.Queue]] = {}
        self._replay_size = replay_size
        self._lock = asyncio.Lock()
        self._closed = False

    async def publish(self, channel: str, event: dict) -> None:
        if self._closed:
            return
        async with self._lock:
            buf = self._replay.setdefault(
                channel, deque(maxlen=self._replay_size)
            )
            buf.append(event)
            subs = list(self._subs.get(channel, []))
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus subscriber queue full for %s, dropping event",
                    channel,
                )

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        """订阅 channel。先快照并重放历史, 再 live 监听。"""
        q: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_QUEUE_MAX)
        async with self._lock:
            # 快照当前 replay (后续 publish 期间产生的事件会进 queue, 不丢)
            replay_snapshot = list(self._replay.get(channel, []))
            self._subs.setdefault(channel, []).append(q)

        try:
            # Phase 1: replay 历史
            for event in replay_snapshot:
                yield event

            # Phase 2: live
            while True:
                event = await q.get()
                if event is _SENTINEL:
                    break
                yield event
        finally:
            async with self._lock:
                subs = self._subs.get(channel, [])
                if q in subs:
                    subs.remove(q)
                if not subs:
                    self._subs.pop(channel, None)

    async def shutdown(self) -> None:
        self._closed = True
        async with self._lock:
            all_subs = list(self._subs.values())
        for subs in all_subs:
            for q in subs:
                try:
                    q.put_nowait(_SENTINEL)
                except asyncio.QueueFull:
                    pass
        async with self._lock:
            self._subs.clear()


# ---------------------------------------------------------------------------
# 后端选择 (按 settings.redis_url)
# ---------------------------------------------------------------------------

# 全局 bus 单例: main.py lifespan 启动时 set_global_bus 注入; 各 manager
# 通过 get_global_bus() 惰性取用, 避免 import 时序问题 (manager 模块加载
# 先于 lifespan)。None = 进程内模式 (单 worker / 单测)。
_global_bus: "EventBus | None" = None


def set_global_bus(bus: "EventBus | None") -> None:
    """lifespan 启动时注入全局 bus; 传 None 重置为进程内模式。"""
    global _global_bus
    _global_bus = bus


def get_global_bus() -> "EventBus | None":
    """取全局 bus; None 表示进程内模式。"""
    return _global_bus


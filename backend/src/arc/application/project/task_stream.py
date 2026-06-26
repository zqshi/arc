"""Project-level task event aggregator.

Collects real-time events from all active conversations within a project
and fans them out to SSE subscribers on the project task-stream endpoint.

多 worker (v6.7): 注入 EventBus 后, emit/subscribe 走 bus channel
`arc:project:{project_id}` 跨进程广播。bus=None 时退回进程内模式。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from arc.infrastructure.eventbus import EventBus

logger = logging.getLogger(__name__)

_SENTINEL = None
_CHANNEL_PREFIX = "arc:project:"


class ProjectTaskStream:
    """Aggregates per-todo events into a project-level SSE stream."""

    def __init__(self, bus: EventBus | None = None):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
        self._explicit_bus = bus

    @property
    def _bus(self) -> EventBus | None:
        if self._explicit_bus is not None:
            return self._explicit_bus
        from arc.infrastructure.eventbus import get_global_bus

        return get_global_bus()

    def _channel(self, project_id: str) -> str:
        return f"{_CHANNEL_PREFIX}{project_id}"

    async def emit(self, project_id: str, event: dict) -> None:
        bus = self._bus
        if bus is not None:
            await bus.publish(self._channel(project_id), event)
            return
        # 进程内: 直接投本地订阅者
        async with self._lock:
            subs = self._subscribers.get(project_id, [])
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        bus = self._bus
        if bus is not None:
            # 多 worker: 经 bus 订阅 (含 replay)
            async for event in bus.subscribe(self._channel(project_id)):
                yield event
            return

        # 进程内模式
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.setdefault(project_id, []).append(queue)
        try:
            while True:
                event = await queue.get()
                if event is _SENTINEL:
                    break
                yield event
        finally:
            async with self._lock:
                subs = self._subscribers.get(project_id, [])
                if queue in subs:
                    subs.remove(queue)
                if not subs:
                    self._subscribers.pop(project_id, None)


project_task_stream = ProjectTaskStream()

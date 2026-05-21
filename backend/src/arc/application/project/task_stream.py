"""Project-level task event aggregator.

Collects real-time events from all active conversations within a project
and fans them out to SSE subscribers on the project task-stream endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

_SENTINEL = None


class ProjectTaskStream:
    """Aggregates per-todo events into a project-level SSE stream."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def emit(self, project_id: str, event: dict) -> None:
        async with self._lock:
            subs = self._subscribers.get(project_id, [])
            for q in subs:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
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

    async def close_project(self, project_id: str) -> None:
        async with self._lock:
            subs = self._subscribers.pop(project_id, [])
            for q in subs:
                try:
                    q.put_nowait(_SENTINEL)
                except asyncio.QueueFull:
                    pass


project_task_stream = ProjectTaskStream()

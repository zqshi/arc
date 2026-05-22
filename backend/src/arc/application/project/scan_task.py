"""Background scan task manager.

Manages per-project async scan tasks with event queues for SSE streaming.
Tasks run independently of client connections — results persist to DB
even if the client disconnects.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncIterator

logger = logging.getLogger(__name__)

_QUEUE_SENTINEL = None


class ScanTaskManager:
    """Manages per-project background codebase scan tasks."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    def is_running(self, project_id: str) -> bool:
        task = self._tasks.get(project_id)
        return task is not None and not task.done()

    async def start_scan(self, project_id: str, path: str) -> str:
        """Start a background scan task. Returns task_id."""
        async with self._lock:
            if self.is_running(project_id):
                raise RuntimeError("Scan already in progress")
            self._queues[project_id] = []
            task_id = str(uuid.uuid4())[:8]
            task = asyncio.create_task(self._run_scan(project_id, path, task_id))
            self._tasks[project_id] = task
            return task_id

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        """Subscribe to scan events for a project. Yields events until done."""
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            subscribers = self._queues.get(project_id)
            if subscribers is None:
                subscribers = []
                self._queues[project_id] = subscribers
            subscribers.append(queue)

        try:
            while True:
                event = await queue.get()
                if event is _QUEUE_SENTINEL:
                    break
                yield event
        finally:
            async with self._lock:
                subs = self._queues.get(project_id, [])
                if queue in subs:
                    subs.remove(queue)

    async def _emit(self, project_id: str, event: dict) -> None:
        async with self._lock:
            subscribers = self._queues.get(project_id, [])
            for q in subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    async def _finish(self, project_id: str) -> None:
        """Signal all subscribers that the scan is done."""
        async with self._lock:
            subscribers = self._queues.get(project_id, [])
            for q in subscribers:
                try:
                    q.put_nowait(_QUEUE_SENTINEL)
                except asyncio.QueueFull:
                    pass

    async def _run_scan(self, project_id: str, path: str, task_id: str) -> None:
        """Execute the scan, emitting events and persisting the result."""
        from arc.application.project.scanner import (
            compute_scan_fingerprint,
            scan_and_summarize_stream,
        )

        logger.info("Scan started for project %s (task=%s)", project_id, task_id)
        summary = ""

        try:
            async for event in scan_and_summarize_stream(path):
                await self._emit(project_id, event)
                if event.get("event") == "done":
                    summary = event.get("summary", "")

            fingerprint = await compute_scan_fingerprint(path)
            await self._persist_result(project_id, summary, fingerprint)
            logger.info("Scan completed for project %s", project_id)

        except Exception as exc:
            logger.error("Scan failed for project %s: %s", project_id, exc)
            await self._emit(
                project_id,
                {
                    "event": "error",
                    "detail": str(exc),
                },
            )
        finally:
            await self._finish(project_id)
            async with self._lock:
                self._tasks.pop(project_id, None)

    async def _persist_result(self, project_id: str, summary: str, fingerprint: str) -> None:
        """Save scan result to database."""
        from uuid import UUID

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository

        async with async_session_factory() as db:
            repo = ProjectRepository(db)
            project = await repo.get_by_id(UUID(project_id))
            if project:
                project.codebase_summary = summary
                project.scan_fingerprint = fingerprint
                await repo.update(project)
                await db.commit()


scan_manager = ScanTaskManager()

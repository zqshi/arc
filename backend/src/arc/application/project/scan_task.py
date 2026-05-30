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
        self._last_error: dict[str, str] = {}  # project_id → error message
        self._lock = asyncio.Lock()

    def is_running(self, project_id: str) -> bool:
        task = self._tasks.get(project_id)
        return task is not None and not task.done()

    def get_last_error(self, project_id: str) -> str | None:
        """Return the last scan error message for a project, or None."""
        return self._last_error.get(project_id)

    async def start_scan(self, project_id: str, path: str) -> str:
        """Start a background scan task. Returns task_id."""
        async with self._lock:
            if self.is_running(project_id):
                raise RuntimeError("Scan already in progress")
            self._queues[project_id] = []
            self._last_error.pop(project_id, None)
            task_id = str(uuid.uuid4())[:8]
            task = asyncio.create_task(self._run_scan(project_id, path, task_id))
            self._tasks[project_id] = task
            return task_id

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        """Subscribe to scan events for a project. Yields events until done.

        If the scan task has already finished (or was never started),
        the generator returns immediately — callers must handle the empty case.
        """
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            # If no task is running, return immediately to avoid blocking forever
            if not self.is_running(project_id):
                return
            subscribers = self._queues.get(project_id)
            if subscribers is None:
                return
            subscribers.append(queue)

        try:
            while True:
                # Timeout prevents permanent blocking if sentinel is somehow lost
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    logger.warning("Scan subscribe timeout for project %s", project_id)
                    break
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
        from arc.application.project.scanner import compute_scan_fingerprint
        from arc.application.project.scanner_analysis import (
            scan_and_summarize_stream,
        )

        logger.info("Scan started for project %s (task=%s)", project_id, task_id)
        summary = ""
        domain_model = None

        try:
            async for event in scan_and_summarize_stream(path):
                await self._emit(project_id, event)
                if event.get("event") == "done":
                    summary = event.get("summary", "")
                elif event.get("event") == "domain_model":
                    domain_model = event.get("domain_model")

            fingerprint = await compute_scan_fingerprint(path)
            await self._persist_result(project_id, summary, fingerprint, domain_model)
            logger.info("Scan completed for project %s", project_id)

        except Exception as exc:
            logger.error("Scan failed for project %s: %s", project_id, exc)
            self._last_error[project_id] = str(exc)
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

    async def _persist_result(
        self, project_id: str, summary: str, fingerprint: str,
        domain_model: dict | None = None,
    ) -> None:
        """Save scan result to database (summary + domain model)."""
        from datetime import UTC, datetime
        from uuid import UUID

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository

        async with async_session_factory() as db:
            repo = ProjectRepository(db)
            project = await repo.get_by_id(UUID(project_id))
            if project:
                project.codebase_summary = summary
                project.scan_fingerprint = fingerprint

                # Merge domain model if extracted
                if domain_model:
                    existing_dm = project.domain_model or {}
                    # If no existing model, use extracted directly
                    if not existing_dm.get("aggregates") and not existing_dm.get("subdomains"):
                        domain_model["updated_at"] = datetime.now(UTC).isoformat()
                        domain_model["version"] = 1
                        domain_model["source"] = "codebase_scan"
                        project.domain_model = domain_model
                    else:
                        # Merge: add new aggregates/subdomains that don't exist
                        self._merge_domain_model(existing_dm, domain_model)
                        existing_dm["updated_at"] = datetime.now(UTC).isoformat()
                        existing_dm["version"] = existing_dm.get("version", 0) + 1
                        project.domain_model = existing_dm

                await repo.update(project)
                await db.commit()

    @staticmethod
    def _merge_domain_model(existing: dict, new: dict) -> None:
        """Merge new scan-extracted model into existing model without losing manual edits."""
        # Merge subdomains by name
        existing_subs = {s.get("name"): s for s in existing.get("subdomains", [])}
        for sd in new.get("subdomains", []):
            name = sd.get("name")
            if name and name not in existing_subs:
                existing_subs[name] = sd
        existing["subdomains"] = list(existing_subs.values())

        # Merge contexts by name
        existing_ctxs = {c.get("name"): c for c in existing.get("contexts", [])}
        for ctx in new.get("contexts", []):
            name = ctx.get("name")
            if name and name not in existing_ctxs:
                existing_ctxs[name] = ctx
        existing["contexts"] = list(existing_ctxs.values())

        # Merge aggregates by name
        existing_aggs = {a.get("name"): a for a in existing.get("aggregates", [])}
        for agg in new.get("aggregates", []):
            name = agg.get("name")
            if not name:
                continue
            if name not in existing_aggs:
                existing_aggs[name] = agg
            else:
                # Update fields/methods from code scan (more accurate)
                old = existing_aggs[name]
                if agg.get("fields"):
                    old["fields"] = agg["fields"]
                if agg.get("methods"):
                    old["methods"] = agg["methods"]
                if agg.get("value_objects"):
                    old["value_objects"] = agg["value_objects"]
        existing["aggregates"] = list(existing_aggs.values())

        # Merge relations (add new ones)
        existing_rels = {(r.get("from"), r.get("to")) for r in existing.get("relations", [])}
        for rel in new.get("relations", []):
            key = (rel.get("from"), rel.get("to"))
            if key not in existing_rels:
                existing.setdefault("relations", []).append(rel)
                existing_rels.add(key)

        existing_agg_rels = {(r.get("from"), r.get("to")) for r in existing.get("aggregate_relations", [])}
        for rel in new.get("aggregate_relations", []):
            key = (rel.get("from"), rel.get("to"))
            if key not in existing_agg_rels:
                existing.setdefault("aggregate_relations", []).append(rel)
                existing_agg_rels.add(key)


scan_manager = ScanTaskManager()

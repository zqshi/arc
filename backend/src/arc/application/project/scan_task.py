"""Background scan task manager.

Manages per-project async scan tasks with event queues for SSE streaming.
Tasks run independently of client connections — results persist to DB
even if the client disconnects.

多 worker (v6.7): _emit/subscribe/_finish 走 EventBus channel
`arc:scan:{project_id}` 跨进程广播。bus=None 时退回进程内模式。
累积内容 (_accumulated) 是业务状态, 留在 manager 本地维护。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING, AsyncIterator

if TYPE_CHECKING:
    from arc.infrastructure.eventbus import EventBus

logger = logging.getLogger(__name__)

_QUEUE_SENTINEL = None
_CHANNEL_PREFIX = "arc:scan:"


class ScanTaskManager:
    """Manages per-project background codebase scan tasks."""

    def __init__(self, bus: EventBus | None = None):
        self._tasks: dict[str, asyncio.Task] = {}
        self._queues: dict[str, list[asyncio.Queue]] = {}
        self._last_error: dict[str, str] = {}  # project_id → error message
        self._accumulated: dict[str, str] = {}  # project_id → accumulated chunk content
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

    def is_running(self, project_id: str) -> bool:
        task = self._tasks.get(project_id)
        return task is not None and not task.done()

    def get_last_error(self, project_id: str) -> str | None:
        """Return the last scan error message for a project, or None."""
        return self._last_error.get(project_id)

    async def start_scan(
        self, project_id: str, path: str, llm_config: dict | None = None
    ) -> str:
        """Start a background scan task. Returns task_id.

        v6.22 B: llm_config 由调用方 (scan_codebase 路由) 经 D1 resolve_from_project
        解析后透传, 扫描走 DB 凭证; None 时 scanner_analysis fallback env.
        """
        async with self._lock:
            if self.is_running(project_id):
                raise RuntimeError("Scan already in progress")
            self._queues[project_id] = []
            self._last_error.pop(project_id, None)
            self._accumulated[project_id] = ""
            task_id = str(uuid.uuid4())[:8]
            task = asyncio.create_task(
                self._run_scan(project_id, path, task_id, llm_config)
            )
            self._tasks[project_id] = task
            return task_id

    async def cancel(self, project_id: str) -> bool:
        """取消正在进行的扫描 task (force=true 强制重扫用)。

        先从 _tasks 移除 (让 is_running 立即 False, start_scan 能进), 再 cancel+await
        让 task 走完 finally (_finish 通知订阅者 + pop)。不在 lock 内 await task
        (避免与 _run_scan finally 的 lock 死锁)。返回是否确实取消了运行中的 task。
        scan_status 残留由 scan_codebase 路由补偿 (置 idle)。
        """
        async with self._lock:
            task = self._tasks.pop(project_id, None)
        if task is None or task.done():
            return False
        task.cancel()
        try:
            await task
        except BaseException:
            pass
        async with self._lock:
            self._accumulated.pop(project_id, None)
        return True

    async def subscribe(self, project_id: str) -> AsyncIterator[dict]:
        """Subscribe to scan events for a project. Yields events until done.

        If the scan task has already finished (or was never started),
        the generator returns immediately — callers must handle the empty case.
        Late subscribers receive accumulated content first, then live events.
        """
        bus = self._bus
        if bus is not None:
            # 多 worker: 经 bus 订阅 (bus 自带 replay 缓冲)
            async for event in bus.subscribe(self._channel(project_id)):
                yield event
            return

        # 进程内模式
        queue: asyncio.Queue = asyncio.Queue()
        accumulated = ""
        async with self._lock:
            # If no task is running, return immediately to avoid blocking forever
            if not self.is_running(project_id):
                return
            subscribers = self._queues.get(project_id)
            if subscribers is None:
                return
            subscribers.append(queue)
            # Snapshot accumulated content under lock
            accumulated = self._accumulated.get(project_id, "")

        # Send accumulated content first so late subscribers see history
        if accumulated:
            yield {"event": "replay", "content": accumulated}

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
        # 累积内容是业务状态, 本地维护 (多 worker 下各 worker 各自累积;
        # replay 由 bus 缓冲承接, accumulated 用于错误时持久化部分内容)
        async with self._lock:
            evt_type = event.get("event")
            if evt_type == "chunk":
                self._accumulated.setdefault(project_id, "")
                self._accumulated[project_id] += event.get("content", "")
            elif evt_type == "done":
                # Replace accumulated with final summary
                self._accumulated[project_id] = event.get("summary", "")

        bus = self._bus
        if bus is not None:
            await bus.publish(self._channel(project_id), event)
            return

        # 进程内: 投本地订阅者
        async with self._lock:
            subscribers = self._queues.get(project_id, [])
        for q in subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _finish(self, project_id: str) -> None:
        """Signal all subscribers that the scan is done."""
        bus = self._bus
        if bus is not None:
            await bus.publish(self._channel(project_id), {"_sentinel": True})
            return

        async with self._lock:
            subscribers = self._queues.get(project_id, [])
        for q in subscribers:
            try:
                q.put_nowait(_QUEUE_SENTINEL)
            except asyncio.QueueFull:
                pass

    async def _run_scan(
        self, project_id: str, path: str, task_id: str, llm_config: dict | None = None
    ) -> None:
        """Execute the scan, emitting events and persisting the result."""
        from arc.application.project.scanner import compute_scan_fingerprint
        from arc.application.project.scanner_analysis import (
            scan_and_summarize_stream,
        )

        logger.info("Scan started for project %s (task=%s)", project_id, task_id)
        summary = ""
        domain_model = None

        # Mark scanning in DB
        await self._update_scan_status(project_id, "start")

        try:
            last_stage = ""
            async for event in scan_and_summarize_stream(path, llm_config):
                await self._emit(project_id, event)
                evt_type = event.get("event")
                if evt_type == "done":
                    summary = event.get("summary", "")
                elif evt_type == "domain_model":
                    domain_model = event.get("domain_model")
                elif evt_type == "stage":
                    stage = event.get("message", "")
                    if stage != last_stage:
                        last_stage = stage
                        await self._update_scan_status(
                            project_id, "progress", stage=stage
                        )

            fingerprint = await compute_scan_fingerprint(path)
            await self._persist_result(project_id, summary, fingerprint, domain_model)
            await self._update_scan_status(
                project_id, "complete", summary=summary, fingerprint=fingerprint
            )
            logger.info("Scan completed for project %s", project_id)

        except Exception as exc:
            logger.error("Scan failed for project %s: %s", project_id, exc)
            self._last_error[project_id] = str(exc)
            # Save partial content so user doesn't lose already-generated text
            partial = self._accumulated.get(project_id, "")
            await self._update_scan_status(
                project_id, "error", error=str(exc), partial_content=partial,
            )
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
                self._accumulated.pop(project_id, None)

    async def _update_scan_status(
        self,
        project_id: str,
        action: str,
        *,
        stage: str = "",
        summary: str = "",
        fingerprint: str = "",
        error: str = "",
        partial_content: str = "",
    ) -> None:
        """Persist scan lifecycle state to DB."""
        from uuid import UUID

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository

        try:
            async with async_session_factory() as db:
                repo = ProjectRepository(db)
                project = await repo.get_by_id(UUID(project_id))
                if not project:
                    return
                if action == "start":
                    project.start_scan()
                elif action == "progress":
                    project.update_scan_progress(stage)
                elif action == "complete":
                    project.complete_scan(summary, fingerprint)
                elif action == "error":
                    project.fail_scan(error)
                    # Preserve partial content so user doesn't lose progress
                    if partial_content:
                        project.codebase_summary = (
                            f"[扫描未完成 — 以下为已生成的部分内容]\n\n{partial_content}"
                        )
                await repo.update(project)
                await db.commit()
        except Exception as exc:
            logger.warning("Failed to update scan status: %s", exc)

    async def _persist_result(
        self, project_id: str, summary: str, fingerprint: str,
        domain_model: dict | None = None,
    ) -> None:
        """Save scan result to database (summary + domain model + diff)."""
        from datetime import UTC, datetime
        from uuid import UUID

        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository

        async with async_session_factory() as db:
            repo = ProjectRepository(db)
            project = await repo.get_by_id(UUID(project_id))
            if project:
                # T7: 计算增量 diff（在覆盖前）
                old_dm = project.domain_model or {}
                old_summary = project.codebase_summary or ""

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

                # T7: 生成 scan diff 并附加到 domain_model 元数据
                scan_diff = self._compute_scan_diff(
                    old_dm, project.domain_model or {},
                    old_summary, summary,
                )
                if scan_diff and project.domain_model:
                    scan_history = project.domain_model.get("_scan_history", [])
                    scan_history.append({
                        "timestamp": datetime.now(UTC).isoformat(),
                        "fingerprint": fingerprint,
                        "diff": scan_diff,
                    })
                    # 只保留最近 10 次 diff 记录
                    project.domain_model["_scan_history"] = scan_history[-10:]
                    project.domain_model["_last_scan_diff"] = scan_diff

                await repo.update(project)
                await db.commit()

    @staticmethod
    def _compute_scan_diff(
        old_dm: dict, new_dm: dict,
        old_summary: str, new_summary: str,
    ) -> dict | None:
        """计算两次扫描之间的领域模型变更。"""
        if not old_dm and not new_dm:
            return None
        if not old_dm:
            # 首次扫描
            return {
                "type": "initial",
                "aggregates_added": len(new_dm.get("aggregates", [])),
                "subdomains_added": len(new_dm.get("subdomains", [])),
                "contexts_added": len(new_dm.get("contexts", [])),
            }

        old_aggs = {a.get("name") for a in old_dm.get("aggregates", []) if a.get("name")}
        new_aggs = {a.get("name") for a in new_dm.get("aggregates", []) if a.get("name")}
        old_subs = {s.get("name") for s in old_dm.get("subdomains", []) if s.get("name")}
        new_subs = {s.get("name") for s in new_dm.get("subdomains", []) if s.get("name")}
        old_ctxs = {c.get("name") for c in old_dm.get("contexts", []) if c.get("name")}
        new_ctxs = {c.get("name") for c in new_dm.get("contexts", []) if c.get("name")}

        added_aggs = new_aggs - old_aggs
        removed_aggs = old_aggs - new_aggs
        added_subs = new_subs - old_subs
        removed_subs = old_subs - new_subs
        added_ctxs = new_ctxs - old_ctxs

        if not any([added_aggs, removed_aggs, added_subs, removed_subs, added_ctxs]):
            # 检查 summary 是否变化
            if old_summary != new_summary:
                return {"type": "summary_only", "summary_changed": True}
            return None

        return {
            "type": "incremental",
            "aggregates_added": sorted(added_aggs),
            "aggregates_removed": sorted(removed_aggs),
            "subdomains_added": sorted(added_subs),
            "subdomains_removed": sorted(removed_subs),
            "contexts_added": sorted(added_ctxs),
            "summary_changed": old_summary != new_summary,
        }

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

        existing_agg_rels = {
            (r.get("from"), r.get("to"))
            for r in existing.get("aggregate_relations", [])
        }
        for rel in new.get("aggregate_relations", []):
            key = (rel.get("from"), rel.get("to"))
            if key not in existing_agg_rels:
                existing.setdefault("aggregate_relations", []).append(rel)
                existing_agg_rels.add(key)


scan_manager = ScanTaskManager()

from __future__ import annotations

import asyncio

import pytest

from arc.application.project.scan_task import ScanTaskManager


class TestScanTaskManager:
    def test_not_running_initially(self) -> None:
        mgr = ScanTaskManager()
        assert mgr.is_running("proj-1") is False

    @pytest.mark.asyncio
    async def test_is_running_after_start(self) -> None:
        mgr = ScanTaskManager()

        async def fake_scan(pid, path, tid):
            await asyncio.sleep(10)

        mgr._run_scan = fake_scan
        await mgr.start_scan("proj-1", "/tmp")
        assert mgr.is_running("proj-1") is True

        task = mgr._tasks["proj-1"]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_cannot_start_twice(self) -> None:
        mgr = ScanTaskManager()

        async def fake_scan(pid, path, tid):
            await asyncio.sleep(10)

        mgr._run_scan = fake_scan
        await mgr.start_scan("proj-1", "/tmp")

        with pytest.raises(RuntimeError, match="already in progress"):
            await mgr.start_scan("proj-1", "/tmp")

        task = mgr._tasks["proj-1"]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

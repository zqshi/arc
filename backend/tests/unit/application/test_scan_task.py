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

        async def fake_scan(pid, path, tid, llm_config=None):
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

        async def fake_scan(pid, path, tid, llm_config=None):
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

    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        """A: cancel 取消运行中的 task, is_running 立即 False."""
        mgr = ScanTaskManager()

        async def fake_scan(pid, path, tid, llm_config=None):
            await asyncio.sleep(10)

        mgr._run_scan = fake_scan
        await mgr.start_scan("proj-1", "/tmp")
        assert mgr.is_running("proj-1") is True

        cancelled = await mgr.cancel("proj-1")
        assert cancelled is True
        assert mgr.is_running("proj-1") is False

    @pytest.mark.asyncio
    async def test_cancel_idle_returns_false(self) -> None:
        """cancel 无运行 task 返回 False."""
        mgr = ScanTaskManager()
        assert await mgr.cancel("nonexistent") is False

    @pytest.mark.asyncio
    async def test_start_scan_passes_llm_config(self) -> None:
        """B: start_scan 透传 llm_config 到 _run_scan (扫描走 DB 凭证)."""
        mgr = ScanTaskManager()
        captured: dict = {}

        async def fake_scan(pid, path, tid, llm_config=None):
            captured["llm_config"] = llm_config

        mgr._run_scan = fake_scan
        await mgr.start_scan("proj-1", "/tmp", {"provider": "openai", "api_key": "sk-x"})
        await asyncio.sleep(0.05)  # 让 fake_scan 执行捕获
        assert captured.get("llm_config") == {"provider": "openai", "api_key": "sk-x"}

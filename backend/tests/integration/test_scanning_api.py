"""Integration tests for project scanning endpoints (v6.23 D3).

scan_manager 是模块级全局单例, 但路由函数内 lazy import (from ... import scan_manager)
每次请求重解析模块属性 → monkeypatch 替换模块属性即可注入 testdouble, 无需重构
(核实推翻 current.md "scan_manager 难 mock 需重构" 判断)。

确定性保证: LLM 凭证解析 (resolve_from_project) 仅解析 config 不触发真实 LLM 调用,
但为隔离 DB LLM provider 状态, 测试 monkeypatch 它返回固定 config; compute_scan_fingerprint
含 mtime_ns (脆弱), 测试 monkeypatch 返回固定串。无真实 GLM 调用, 测试确定性。
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from arc.infrastructure.repositories.project import ProjectRepository

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
FIXED_FINGERPRINT = "fp-test-fixed"


class FakeScanManager:
    """ScanTaskManager testdouble — 实现 5 个路由消费的方法, 状态可控。"""

    def __init__(self) -> None:
        self.running = False
        self.last_error: str | None = None
        self.events: list[dict] = []
        self.start_calls: list[tuple] = []
        self.cancel_calls: list[str] = []
        self.start_task_id = "fake-task-1"

    def is_running(self, project_id: str) -> bool:
        return self.running

    def get_last_error(self, project_id: str) -> str | None:
        return self.last_error

    async def start_scan(self, project_id, path, llm_config=None) -> str:
        self.start_calls.append((project_id, path, llm_config))
        return self.start_task_id

    async def cancel(self, project_id: str) -> bool:
        self.cancel_calls.append(project_id)
        return True

    async def subscribe(self, project_id: str):
        for evt in self.events:
            yield evt


@pytest.fixture
def fake_scan_manager(monkeypatch: pytest.MonkeyPatch) -> FakeScanManager:
    """替换 scan_task.scan_manager 模块属性 (路由 lazy import 取此属性)。"""
    fake = FakeScanManager()
    monkeypatch.setattr("arc.application.project.scan_task.scan_manager", fake)
    return fake


@pytest.fixture
def fixed_fingerprint(monkeypatch: pytest.MonkeyPatch) -> str:
    """compute_scan_fingerprint → 固定串 (避 mtime_ns 脆弱)。"""
    async def _fake(_path: str) -> str:
        return FIXED_FINGERPRINT
    monkeypatch.setattr(
        "arc.application.project.scanner.compute_scan_fingerprint", _fake
    )
    return FIXED_FINGERPRINT


@pytest.fixture
def fixed_llm_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_from_project → 固定 config (隔离 DB LLM provider 状态, 避真实调用)。"""
    monkeypatch.setattr(
        "arc.application.llm.service.LLMProviderService.resolve_from_project",
        AsyncMock(return_value={"model": "test-model", "api_key": "test"}),
    )


@pytest.fixture
async def project_for_scan(client: AsyncClient) -> str:
    """创建项目 (默认 temporary workspace → service 建真实 workspace 目录 + 设 local_path,
    不触发 _background_scan 仅 LOCAL 触发)。"""
    resp = await client.post("/api/projects", json={"name": "Scan Test"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


class TestScanningStatus:
    """GET /scan-codebase/status — 运行态查询 + stale 状态补偿。"""

    async def test_status_404_unknown_project(
        self, client: AsyncClient, fake_scan_manager
    ):
        resp = await client.get(
            f"/api/projects/{uuid.uuid4()}/scan-codebase/status"
        )
        assert resp.status_code == 404

    async def test_status_idle_for_fresh_project(
        self, client: AsyncClient, project_for_scan, fake_scan_manager
    ):
        pid = project_for_scan
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["running"] is False
        assert body["scan_status"] == "idle"

    async def test_status_reports_running_when_scan_active(
        self, client: AsyncClient, project_for_scan, fake_scan_manager
    ):
        pid = project_for_scan
        fake_scan_manager.running = True
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/status")
        assert resp.status_code == 200
        assert resp.json()["running"] is True

    async def test_status_cleans_stale_scanning_state(
        self, client: AsyncClient, db_session, project_for_scan, fake_scan_manager
    ):
        """scan_status='scanning' 但 scan_manager 未运行 → 路由补偿置 idle (防崩溃残留)。"""
        pid = project_for_scan
        repo = ProjectRepository(db_session)
        proj = await repo.get_by_id(uuid.UUID(pid), user_id=TEST_USER_ID)
        assert proj is not None
        proj.start_scan()  # 置 scan_status='scanning'
        await repo.update(proj)
        await db_session.flush()

        fake_scan_manager.running = False  # manager 实际未运行
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/status")
        assert resp.status_code == 200
        assert resp.json()["scan_status"] == "idle"  # 补偿后


class TestScanningStart:
    """POST /scan-codebase — 扫描启动 + 缓存 + 冲突。"""

    async def test_start_404_unknown_project(
        self, client: AsyncClient, fake_scan_manager, fixed_llm_config
    ):
        resp = await client.post(f"/api/projects/{uuid.uuid4()}/scan-codebase")
        assert resp.status_code == 404

    async def test_start_400_no_local_path(
        self, client: AsyncClient, fake_scan_manager, fixed_llm_config
    ):
        """项目无 local_path → 400 (workspace_type=local + 空 path → local_path 保持空,
        且 LOCAL+空 path 不触发 _background_scan)。"""
        resp = await client.post(
            "/api/projects", json={"name": "No Path", "workspace_type": "local"}
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]
        resp = await client.post(f"/api/projects/{pid}/scan-codebase")
        assert resp.status_code == 400
        assert "工作目录" in resp.json()["detail"]

    async def test_start_400_dir_not_exist(
        self, client: AsyncClient, db_session, project_for_scan,
        fake_scan_manager, fixed_llm_config,
    ):
        """local_path 指向不存在目录 → 400 (repo 直改 local_path, 绕过 LOCAL create 校验)。"""
        pid = project_for_scan
        repo = ProjectRepository(db_session)
        proj = await repo.get_by_id(uuid.UUID(pid), user_id=TEST_USER_ID)
        assert proj is not None
        proj.local_path = "/nonexistent/path/xyz"
        await repo.update(proj)
        await db_session.flush()
        resp = await client.post(f"/api/projects/{pid}/scan-codebase")
        assert resp.status_code == 400
        assert "目录不存在" in resp.json()["detail"]

    async def test_start_202_fresh_scan(
        self, client: AsyncClient, db_session, project_for_scan,
        fake_scan_manager, fixed_llm_config,
    ):
        pid = project_for_scan
        resp = await client.post(f"/api/projects/{pid}/scan-codebase")
        assert resp.status_code == 202
        body = resp.json()
        assert body["task_id"] == "fake-task-1"
        assert body["status"] == "running"
        # start_scan 收到 pid + 解析后的 path + llm_config
        assert len(fake_scan_manager.start_calls) == 1
        called_pid, called_path, called_llm = fake_scan_manager.start_calls[0]
        assert called_pid == pid
        assert called_llm == {"model": "test-model", "api_key": "test"}
        # called_path = 项目 local_path 的 resolve 形式 (temporary workspace 目录)
        repo = ProjectRepository(db_session)
        proj = await repo.get_by_id(uuid.UUID(pid), user_id=TEST_USER_ID)
        assert proj is not None
        assert called_path == str(Path(proj.local_path).expanduser().resolve())

    async def test_start_200_cached_when_fingerprint_matches(
        self, client: AsyncClient, db_session, project_for_scan,
        fake_scan_manager, fixed_fingerprint, fixed_llm_config,
    ):
        """非 force + 已有 summary + fingerprint 匹配 → 200 cached (跳过扫描)。"""
        pid = project_for_scan
        repo = ProjectRepository(db_session)
        proj = await repo.get_by_id(uuid.UUID(pid), user_id=TEST_USER_ID)
        assert proj is not None
        proj.complete_scan("existing summary", FIXED_FINGERPRINT)
        await repo.update(proj)
        await db_session.flush()

        resp = await client.post(f"/api/projects/{pid}/scan-codebase")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cached"] is True
        assert body["summary"] == "existing summary"
        assert fake_scan_manager.start_calls == []  # 未触发扫描

    async def test_start_409_when_already_running(
        self, client: AsyncClient, project_for_scan, fake_scan_manager,
        fixed_llm_config,
    ):
        pid = project_for_scan
        fake_scan_manager.running = True
        resp = await client.post(f"/api/projects/{pid}/scan-codebase")
        assert resp.status_code == 409
        assert "重复" in resp.json()["detail"]
        assert fake_scan_manager.start_calls == []

    async def test_start_force_cancels_running_then_starts(
        self, client: AsyncClient, project_for_scan, fake_scan_manager,
        fixed_llm_config,
    ):
        """force=true + 运行中 → 取消旧 task 后再启动 (v6.22 T8 强制重扫)。"""
        pid = project_for_scan
        fake_scan_manager.running = True
        resp = await client.post(
            f"/api/projects/{pid}/scan-codebase", params={"force": True}
        )
        assert resp.status_code == 202
        assert fake_scan_manager.cancel_calls == [pid]
        assert len(fake_scan_manager.start_calls) == 1


class TestScanningStream:
    """GET /scan-codebase/stream — SSE 事件流。"""

    async def test_stream_404_unknown_project(
        self, client: AsyncClient, fake_scan_manager
    ):
        resp = await client.get(
            f"/api/projects/{uuid.uuid4()}/scan-codebase/stream"
        )
        assert resp.status_code == 404

    async def test_stream_yields_done_when_no_events(
        self, client: AsyncClient, project_for_scan, fake_scan_manager
    ):
        """无事件 + 无错误 → done 事件 + close。"""
        pid = project_for_scan
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/stream")
        assert resp.status_code == 200
        assert "event: done" in resp.text
        assert "event: close" in resp.text

    async def test_stream_yields_error_when_last_error_set(
        self, client: AsyncClient, project_for_scan, fake_scan_manager
    ):
        """无事件 + last_error → error 事件 + close。"""
        pid = project_for_scan
        fake_scan_manager.last_error = "scan failed: boom"
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/stream")
        assert resp.status_code == 200
        assert "event: error" in resp.text
        assert "boom" in resp.text
        assert "event: close" in resp.text

    async def test_stream_replays_events_from_subscribe(
        self, client: AsyncClient, project_for_scan, fake_scan_manager
    ):
        """subscribe 有事件 → 透传 chunk 事件 + close (不走 done/error 分支)。"""
        pid = project_for_scan
        fake_scan_manager.events = [
            {"event": "chunk", "content": "hello"},
            {"event": "done", "summary": "extracted"},
        ]
        resp = await client.get(f"/api/projects/{pid}/scan-codebase/stream")
        assert resp.status_code == 200
        # 透传的 chunk
        assert "event: chunk" in resp.text
        assert "hello" in resp.text
        # 透传的 done (来自 subscribe, 非路由兜底)
        assert '"event": "done"' in resp.text
        assert "event: close" in resp.text

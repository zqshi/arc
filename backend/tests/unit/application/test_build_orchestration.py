"""Tests for application/build/orchestration — CI 构建编排 (v6.19 T3-d/T3-g 设计2-3)。

dispatch_build (立即返回, 记录 building) + await_build (后台 poll/download/记录
success/failed) 分离, 供 build 工具异步编排 (CI 不阻塞 Agent 对话)。

blocked 期不真实联调。用 fake client (控 list_runs/artifacts/download 返回) +
mock artifact_service + fake zip + tmp_path 验证 dispatch/await 契约。
"""

import io
import zipfile
from unittest.mock import AsyncMock

import pytest

from arc.application.build.orchestration import BuildOrchestrationService
from arc.domain.errors import AppError
from arc.domain.sandbox.value_objects import BuildTarget

SRC_URL = "https://storage.example/test-src.tar.gz"


def _fake_zip(filenames: list[str]) -> bytes:
    """构造含指定文件的合法 zip (供 _download_and_extract 解压)。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in filenames:
            zf.writestr(name, b"fake-content")
    return buf.getvalue()


class FakeClient:
    """可控的 GHA client 替身 — 记录 dispatch, 按预设返回 runs/artifacts/zip。"""

    def __init__(self, *, runs, artifacts=None, zip_data=b""):
        self.dispatched = []
        self._runs = runs
        self._artifacts = artifacts or []
        self._zip = zip_data

    async def dispatch_workflow(self, workflow_filename, ref="main", inputs=None):
        self.dispatched.append((workflow_filename, inputs))

    async def list_runs(self, *, event=None, per_page=1):
        return self._runs

    async def list_artifacts(self, run_id):
        return self._artifacts

    async def download_artifact(self, artifact_id):
        return self._zip


def _make_service(client, artifact_svc=None):
    return BuildOrchestrationService(db=None, client=client, artifact_service=artifact_svc)


class TestDispatchBuild:
    """dispatch_build: dispatch workflow + 记录 BUILD(building), 立即返回 (不 poll/download)。"""

    @pytest.mark.asyncio
    async def test_dispatches_workflow_and_records_building(self):
        """dispatch(含 source_url) + create_or_update_build(building), 立即返回。"""
        client = FakeClient(runs=[])  # dispatch_build 不 poll, runs 不用
        artifact_svc = AsyncMock()
        svc = _make_service(client, artifact_svc)

        await svc.dispatch_build(
            BuildTarget.TAURI_WINDOWS,
            todo_id="todo-1",
            phase_id="phase-1",
            source_url=SRC_URL,
        )

        # dispatch 被调, inputs 含 build_target + source_url (CI 据此下载代码构建)
        assert client.dispatched == [
            ("build-client-artifacts.yml", {"build_target": "tauri_windows", "source_url": SRC_URL})
        ]
        # BUILD artifact 记录 building (供前端/Agent 知构建进行中)
        artifact_svc.create_or_update_build.assert_awaited_once()
        call = artifact_svc.create_or_update_build.await_args
        assert call.kwargs["build_target"] == "tauri_windows"
        assert call.kwargs["build_status"] == "building"
        assert call.kwargs["todo_id"] == "todo-1"

    @pytest.mark.asyncio
    async def test_docker_target_rejected(self):
        """DOCKER target 不走编排 → AppError, 未 dispatch (T1: CI 编排仅 CI target)。"""
        client = FakeClient(runs=[])
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="仅编排 CI target"):
            await svc.dispatch_build(
                BuildTarget.TAURI_LINUX,  # DOCKER target
                todo_id="t",
                phase_id="p",
                source_url=SRC_URL,
            )
        assert client.dispatched == []  # 未触发 dispatch


class TestAwaitBuild:
    """await_build: 轮询 CI run → 下载产物 → 记录 BUILD(success/failed)。后台 task 调此。"""

    @pytest.mark.asyncio
    async def test_poll_download_record_success(self, tmp_path):
        """happy path: poll(completed/success) → download/extract → BUILD(success)。"""
        client = FakeClient(
            runs=[{"id": 1, "status": "completed", "conclusion": "success"}],
            artifacts=[{"id": 7, "name": "windows-msi"}, {"id": 8, "name": "windows-exe"}],
            zip_data=_fake_zip(["setup.msi", "setup.exe"]),
        )
        artifact_svc = AsyncMock()
        artifact_svc.create_or_update_build.return_value = "BUILD_ARTIFACT"
        svc = _make_service(client, artifact_svc)

        result = await svc.await_build(
            BuildTarget.TAURI_WINDOWS,
            todo_id="todo-1",
            phase_id="phase-1",
            local_dir=str(tmp_path),
            poll_interval=0,
        )

        # 产物解压到 local_dir/ci-products
        assert (tmp_path / "ci-products" / "setup.msi").is_file()
        assert (tmp_path / "ci-products" / "setup.exe").is_file()
        # BUILD artifact 记录 success + 产物路径
        artifact_svc.create_or_update_build.assert_awaited_once()
        call = artifact_svc.create_or_update_build.await_args
        assert call.kwargs["build_target"] == "tauri_windows"
        assert call.kwargs["build_status"] == "success"
        assert "ci-products" in call.kwargs["artifact_path"]
        assert result == "BUILD_ARTIFACT"

    @pytest.mark.asyncio
    async def test_failed_run_records_failed_status(self):
        """CI run conclusion=failure → BUILD artifact build_status=failed, 不下载产物。"""
        client = FakeClient(
            runs=[{"id": 2, "status": "completed", "conclusion": "failure"}],
        )
        artifact_svc = AsyncMock()
        artifact_svc.create_or_update_build.return_value = "FAILED_ARTIFACT"
        svc = _make_service(client, artifact_svc)

        result = await svc.await_build(
            BuildTarget.TAURI_WINDOWS,
            todo_id="todo-1",
            phase_id="phase-1",
            local_dir="/tmp/unused",  # 失败路径不下载, 不解压
            poll_interval=0,
        )

        call = artifact_svc.create_or_update_build.await_args
        assert call.kwargs["build_status"] == "failed"
        assert call.kwargs["artifact_path"] == ""
        assert "run 2" in call.kwargs["build_log"]
        assert "failure" in call.kwargs["build_log"]
        assert result == "FAILED_ARTIFACT"

    @pytest.mark.asyncio
    async def test_docker_target_rejected(self):
        """await_build: DOCKER target → AppError (防误调)。"""
        svc = _make_service(FakeClient(runs=[]), AsyncMock())
        with pytest.raises(AppError, match="仅编排 CI target"):
            await svc.await_build(
                BuildTarget.TAURI_LINUX,
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
            )

    @pytest.mark.asyncio
    async def test_poll_timeout(self):
        """run 一直 in_progress → 轮询超时 AppError。"""
        client = FakeClient(runs=[{"id": 3, "status": "in_progress", "conclusion": None}])
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="轮询超时"):
            await svc.await_build(
                BuildTarget.TAURI_WINDOWS,
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
                poll_interval=0,
                poll_timeout=0,  # 立即超时
            )

    @pytest.mark.asyncio
    async def test_completed_run_without_artifacts_raises(self):
        """run success 但无 artifact → AppError (产物缺失, 构建异常)。"""
        client = FakeClient(
            runs=[{"id": 4, "status": "completed", "conclusion": "success"}],
            artifacts=[],
        )
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="无 artifact"):
            await svc.await_build(
                BuildTarget.TAURI_WINDOWS,
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
                poll_interval=0,
            )

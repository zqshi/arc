"""Tests for application/build/orchestration — CI 构建编排 (v6.19 T3-d)。

blocked 期不真实联调。用 fake client (控 list_runs/artifacts/download 返回) +
mock artifact_service + fake zip + tmp_path 验证 dispatch/poll/download/记录 契约。
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


class TestOrchestrateSuccess:
    async def test_dispatch_poll_download_record(self, tmp_path):
        """happy path: dispatch(含 source_url) → poll(completed/success) → download/extract → BUILD(success)。"""
        client = FakeClient(
            runs=[{"id": 1, "status": "completed", "conclusion": "success"}],
            artifacts=[{"id": 7, "name": "windows-msi"}, {"id": 8, "name": "windows-exe"}],
            zip_data=_fake_zip(["setup.msi", "setup.exe"]),
        )
        artifact_svc = AsyncMock()
        artifact_svc.create_or_update_build.return_value = "BUILD_ARTIFACT"

        svc = _make_service(client, artifact_svc)
        result = await svc.orchestrate(
            BuildTarget.TAURI_WINDOWS,
            todo_id="todo-1",
            phase_id="phase-1",
            local_dir=str(tmp_path),
            source_url=SRC_URL,
            poll_interval=0,
        )

        # dispatch 被调, inputs 含 build_target + source_url (CI 据此下载代码构建)
        assert client.dispatched == [
            ("build-client-artifacts.yml", {"build_target": "tauri_windows", "source_url": SRC_URL})
        ]
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


class TestOrchestrateFailure:
    async def test_failed_run_records_failed_status(self):
        """CI run conclusion=failure → BUILD artifact build_status=failed, 不下载产物。"""
        client = FakeClient(
            runs=[{"id": 2, "status": "completed", "conclusion": "failure"}],
        )
        artifact_svc = AsyncMock()
        artifact_svc.create_or_update_build.return_value = "FAILED_ARTIFACT"

        svc = _make_service(client, artifact_svc)
        result = await svc.orchestrate(
            BuildTarget.TAURI_WINDOWS,
            todo_id="todo-1",
            phase_id="phase-1",
            local_dir="/tmp/unused",  # 失败路径不下载, 不解压
            source_url=SRC_URL,
            poll_interval=0,
        )
        call = artifact_svc.create_or_update_build.await_args
        assert call.kwargs["build_status"] == "failed"
        assert call.kwargs["artifact_path"] == ""
        assert "run 2" in call.kwargs["build_log"]
        assert "failure" in call.kwargs["build_log"]
        assert result == "FAILED_ARTIFACT"


class TestNonCiTarget:
    async def test_docker_target_rejected(self):
        """DOCKER target 不走编排 → AppError (防误调, T1: CI 编排仅 CI target)。"""
        client = FakeClient(runs=[])
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="仅编排 CI target"):
            await svc.orchestrate(
                BuildTarget.TAURI_LINUX,  # DOCKER target
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
                source_url=SRC_URL,
            )
        assert client.dispatched == []  # 未触发 dispatch


class TestPollTimeout:
    async def test_in_progress_run_times_out(self):
        """run 一直 in_progress → 轮询超时 AppError。"""
        client = FakeClient(runs=[{"id": 3, "status": "in_progress", "conclusion": None}])
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="轮询超时"):
            await svc.orchestrate(
                BuildTarget.TAURI_WINDOWS,
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
                source_url=SRC_URL,
                poll_interval=0,
                poll_timeout=0,  # 立即超时
            )


class TestNoArtifact:
    async def test_completed_run_without_artifacts_raises(self):
        """run success 但无 artifact → AppError (产物缺失, 构建异常)。"""
        client = FakeClient(
            runs=[{"id": 4, "status": "completed", "conclusion": "success"}],
            artifacts=[],
        )
        svc = _make_service(client, AsyncMock())
        with pytest.raises(AppError, match="无 artifact"):
            await svc.orchestrate(
                BuildTarget.TAURI_WINDOWS,
                todo_id="t",
                phase_id="p",
                local_dir="/tmp/x",
                source_url=SRC_URL,
                poll_interval=0,
            )

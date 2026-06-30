"""Tests for build_tool — CI target build Agent 工具 (v6.19 T3-g 设计2)。

mock _upload_source/_dispatch/_background_await 验证 build handler 契约:
dispatch_build 调用 + 后台 task 启动 + 返回"已派发"。docker target 不注册。
"""
from __future__ import annotations

import io
import tarfile
import uuid
from unittest.mock import AsyncMock

import pytest

from arc.application.execution.build_tool import _make_tarball, make_build_tool
from arc.domain.sandbox.value_objects import BuildTarget


class TestMakeBuildTool:
    def test_docker_target_returns_none(self):
        """docker target 不注册 build 工具 (用 run_command, 零改动)。"""
        tool = make_build_tool(
            build_target=BuildTarget.TAURI_LINUX,
            todo_id=uuid.uuid4(),
            db=None,
            conversation_id="c",
            local_dir="/tmp",
        )
        assert tool is None

    def test_ci_target_returns_build_tool(self):
        """CI target 返回 build ToolDefinition。"""
        tool = make_build_tool(
            build_target=BuildTarget.TAURI_WINDOWS,
            todo_id=uuid.uuid4(),
            db=None,
            conversation_id="c",
            local_dir="/tmp",
        )
        assert tool is not None
        assert tool.name == "build"

    @pytest.mark.asyncio
    async def test_build_dispatches_and_starts_background(self, monkeypatch, tmp_path):
        """build handler: upload+presigned → dispatch_build → 启动后台 task → 返回"已派发"。"""

        async def fake_upload(ld, tid):
            return "https://presigned/src.tar.gz"

        monkeypatch.setattr(
            "arc.application.execution.build_tool._upload_source", fake_upload
        )

        dispatched = []

        async def fake_dispatch(target, db, tid, url):
            dispatched.append((target, tid, url))

        monkeypatch.setattr(
            "arc.application.execution.build_tool._dispatch", fake_dispatch
        )

        bg_await = AsyncMock()
        monkeypatch.setattr(
            "arc.application.execution.build_tool._background_await", bg_await
        )

        created = []

        def fake_create_task(coro):
            created.append(coro)
            coro.close()  # 避免未 await warning
            return None

        monkeypatch.setattr(
            "arc.application.execution.build_tool.asyncio.create_task",
            fake_create_task,
        )

        tid = uuid.uuid4()
        tool = make_build_tool(
            build_target=BuildTarget.TAURI_WINDOWS,
            todo_id=tid,
            db=None,
            conversation_id="c1",
            local_dir=str(tmp_path),
        )
        result = await tool.handler({})

        assert "已派发" in result
        assert "tauri_windows" in result
        assert dispatched == [
            (BuildTarget.TAURI_WINDOWS, tid, "https://presigned/src.tar.gz")
        ]
        bg_await.assert_called_once_with(
            BuildTarget.TAURI_WINDOWS, tid, str(tmp_path), "c1"
        )
        assert len(created) == 1  # 后台 task 启动


class TestMakeTarball:
    def test_excludes_large_dirs(self, tmp_path):
        """_make_tarball 排除 node_modules/target/dist 等 (减小体积)。"""
        (tmp_path / "src.txt").write_text("keep")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.js").write_text("exclude")
        (tmp_path / "target").mkdir()
        (tmp_path / "target" / "out.bin").write_text("exclude")

        data = _make_tarball(str(tmp_path))
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            names = tf.getnames()

        assert "src.txt" in names
        assert not any("node_modules" in n for n in names)
        assert not any(n.startswith("target") for n in names)

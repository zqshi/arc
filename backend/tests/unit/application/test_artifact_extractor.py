from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.artifact_extractor import (
    DELIVERABLE_PATTERN,
    ArtifactExtractor,
)
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.project.value_objects import ProjectType


class TestDeliverablePattern:
    def test_matches_standard_marker(self) -> None:
        text = """Some discussion here.

[DELIVERABLE:requirement_spec]
```json
{"background": "test", "goals": ["g1"]}
```

More text."""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0][0] == "requirement_spec"
        assert '"background"' in matches[0][1]

    def test_matches_without_json_lang(self) -> None:
        text = """[DELIVERABLE:test_report]
```
{"summary": "all passed"}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert matches[0][0] == "test_report"

    def test_matches_multiple_markers(self) -> None:
        text = """[DELIVERABLE:requirement_spec]
```json
{"a": 1}
```

Some text between.

[DELIVERABLE:tech_architecture]
```json
{"b": 2}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 2
        assert matches[0][0] == "requirement_spec"
        assert matches[1][0] == "tech_architecture"

    def test_no_match_without_marker(self) -> None:
        text = "Just a normal response without any deliverables."
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 0


class TestAppCodeServiceSpecExtraction:
    """v5.5.0: 验证 ArtifactExtractor 能识别 app_code / service_spec 标记。

    这两个新 artifact 类型走与既有类型相同的 DELIVERABLE 提取链路，
    只要 ArtifactType 枚举包含它们 (T1/T2 已加)，提取即可成功。
    """

    def test_app_code_marker_recognized_as_valid_type(self) -> None:
        """[DELIVERABLE:app_code] 的 type 字符串能转为 ArtifactType。"""
        text = """[DELIVERABLE:app_code]
```json
{"project_dir": "generated/app", "tech_stack": ["react"], "build_command": "npm run build", "run_command": "npm run dev", "entry_points": ["src/main.tsx"]}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        type_str = matches[0][0]
        # 提取链路的关键: ArtifactType(type_str) 不抛 ValueError
        assert ArtifactType(type_str) == ArtifactType.APP_CODE

    def test_service_spec_marker_recognized_as_valid_type(self) -> None:
        """[DELIVERABLE:service_spec] 的 type 字符串能转为 ArtifactType。"""
        text = """[DELIVERABLE:service_spec]
```json
{"data_model_ref": "v1", "data_persistence": "none", "endpoints": [], "auth_strategy": "none"}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert ArtifactType(matches[0][0]) == ArtifactType.SERVICE_SPEC

    def test_build_marker_recognized_as_valid_type(self) -> None:
        """v6.9: [DELIVERABLE:build] 的 type 字符串能转为 ArtifactType。

        构建产物 BUILD 走与既有类型相同的 DELIVERABLE 提取链路, 枚举已含(T1),
        提取自动支持。agent 在 DEVELOPMENT 阶段构建后产出 [DELIVERABLE:build]。
        """
        text = """[DELIVERABLE:build]
```json
{"build_target": "tauri_linux", "artifact_path": "dist", "build_status": "success"}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 1
        assert ArtifactType(matches[0][0]) == ArtifactType.BUILD


class TestProduceBuildArtifact:
    """v6.9: extractor 从 prototype content 抽产出 BUILD artifact(方案B, BINARY_APP)。"""

    @pytest.mark.asyncio
    async def test_binary_app_with_build_status_produces_build(self):
        todo_id = uuid.uuid4()
        prototype = Artifact(
            todo_id=todo_id,
            artifact_type=ArtifactType.PROTOTYPE,
            content={"build_status": "success", "artifact_path": "dist"},
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()

        with (
            patch("arc.infrastructure.repositories.todo.TodoRepository") as todo_repo,
            patch("arc.infrastructure.repositories.project.ProjectRepository") as proj_repo,
            patch("arc.application.artifact.service.ArtifactService") as art_svc,
        ):
            todo_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_id=uuid.uuid4())
            )
            proj_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_type=ProjectType.BINARY_APP)
            )
            art_svc_inst = AsyncMock()
            art_svc.return_value = art_svc_inst

            await svc._try_produce_build_artifact(todo_id, prototype)

            art_svc.assert_called_once_with(svc.db)
            art_svc_inst.create_or_update_build.assert_awaited_once()
            kwargs = art_svc_inst.create_or_update_build.call_args.kwargs
            assert kwargs["build_target"] == "tauri_linux"
            assert kwargs["build_status"] == "success"
            assert kwargs["artifact_path"] == "dist"
            assert kwargs["todo_id"] == todo_id

    @pytest.mark.asyncio
    async def test_static_site_skips_build(self):
        """STATIC_SITE 走 dist 静态站点部署, 无 build_target, 不产出 BUILD。"""
        todo_id = uuid.uuid4()
        prototype = Artifact(
            todo_id=todo_id,
            artifact_type=ArtifactType.PROTOTYPE,
            content={"build_status": "success", "artifact_path": "dist"},
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()

        with (
            patch("arc.infrastructure.repositories.todo.TodoRepository") as todo_repo,
            patch("arc.infrastructure.repositories.project.ProjectRepository") as proj_repo,
            patch("arc.application.artifact.service.ArtifactService") as art_svc,
        ):
            todo_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_id=uuid.uuid4())
            )
            proj_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_type=ProjectType.STATIC_SITE)
            )
            art_svc.return_value.create_or_update_build = AsyncMock()

            await svc._try_produce_build_artifact(todo_id, prototype)

            art_svc.return_value.create_or_update_build.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_build_status_skips(self):
        """prototype content 无 build_status → 不产出 BUILD(无构建信息)。"""
        todo_id = uuid.uuid4()
        prototype = Artifact(
            todo_id=todo_id,
            artifact_type=ArtifactType.PROTOTYPE,
            content={"artifact_path": "dist"},
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()

        with (
            patch("arc.infrastructure.repositories.todo.TodoRepository") as todo_repo,
            patch("arc.infrastructure.repositories.project.ProjectRepository") as proj_repo,
            patch("arc.application.artifact.service.ArtifactService") as art_svc,
        ):
            todo_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_id=uuid.uuid4())
            )
            proj_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_type=ProjectType.BINARY_APP)
            )
            art_svc.return_value.create_or_update_build = AsyncMock()

            await svc._try_produce_build_artifact(todo_id, prototype)

            art_svc.return_value.create_or_update_build.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reads_project_build_target_not_hardcoded(self):
        """v6.19 T3-g 设计4: _try_produce 读 project 实际 build_target (去 TAURI_LINUX 硬编码)。

        docker target (WEB/APK) 不再被误记 tauri_linux; CI target 不走此 (prototype 无 build_status)。
        """
        todo_id = uuid.uuid4()
        prototype = Artifact(
            todo_id=todo_id,
            artifact_type=ArtifactType.PROTOTYPE,
            content={"build_status": "success", "artifact_path": "dist"},
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()

        with (
            patch("arc.infrastructure.repositories.todo.TodoRepository") as todo_repo,
            patch("arc.infrastructure.repositories.project.ProjectRepository") as proj_repo,
            patch("arc.application.artifact.service.ArtifactService") as art_svc,
        ):
            todo_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(project_id=uuid.uuid4())
            )
            proj_repo.return_value.get_by_id = AsyncMock(
                return_value=SimpleNamespace(
                    project_type=ProjectType.BINARY_APP,
                    conversation_config={"sandbox": {"target": "web"}},
                )
            )
            art_svc_inst = AsyncMock()
            art_svc.return_value = art_svc_inst

            await svc._try_produce_build_artifact(todo_id, prototype)

            kwargs = art_svc_inst.create_or_update_build.call_args.kwargs
            assert kwargs["build_target"] == "web"

    def test_dev_report_and_app_code_coexist_in_one_message(self) -> None:
        """DEVELOPMENT 阶段一条消息同时产出 DEV_REPORT + APP_CODE。"""
        text = """[DELIVERABLE:dev_report]
```json
{"test_design": {}, "implementation": {}, "validation": {}}
```

[DELIVERABLE:app_code]
```json
{"project_dir": "gen/app", "tech_stack": ["vue"], "build_command": "npm run build", "run_command": "npm run dev", "entry_points": ["src/main.ts"]}
```"""
        matches = DELIVERABLE_PATTERN.findall(text)
        assert len(matches) == 2
        types = [m[0] for m in matches]
        assert "dev_report" in types
        assert "app_code" in types


class TestProcessMessageTypeFilter:
    """v6.9: process_message 按项目类型过滤 — 非app类不产出 app_code。"""

    @pytest.mark.asyncio
    async def test_static_site_skips_app_code(self):
        content = (
            '[DELIVERABLE:app_code]\n```json\n'
            '{"project_dir":"x","tech_stack":[],"build_command":"",'
            '"run_command":"","entry_points":[]}\n```'
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()
        svc.tracker_repo = MagicMock()
        svc.tracker_repo.get_by_todo_id = AsyncMock(return_value=None)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.upsert_by_type = AsyncMock(side_effect=lambda a: a)
        svc._get_constraint = AsyncMock(return_value=None)
        svc._get_project_type = AsyncMock(return_value=ProjectType.STATIC_SITE)

        result = await svc.process_message(content, uuid.uuid4())

        assert result == []  # app_code 被类型过滤, 无产出
        svc.artifact_repo.upsert_by_type.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_binary_app_extracts_app_code(self):
        content = (
            '[DELIVERABLE:app_code]\n```json\n'
            '{"project_dir":"x","tech_stack":["react"],'
            '"build_command":"npm run build","run_command":"npm run dev",'
            '"entry_points":["src/main.tsx"]}\n```'
        )
        svc = ArtifactExtractor.__new__(ArtifactExtractor)
        svc.db = AsyncMock()
        svc.tracker_repo = MagicMock()
        svc.tracker_repo.get_by_todo_id = AsyncMock(return_value=None)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.upsert_by_type = AsyncMock(side_effect=lambda a: a)
        svc._get_constraint = AsyncMock(return_value=None)
        svc._get_project_type = AsyncMock(return_value=ProjectType.BINARY_APP)

        result = await svc.process_message(content, uuid.uuid4())

        assert len(result) == 1
        assert result[0].artifact_type == ArtifactType.APP_CODE
        svc.artifact_repo.upsert_by_type.assert_awaited_once()


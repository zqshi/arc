"""Tests for Supabase config injection into frontend (v5.6.0 T12).

PrototypeDeployer 在部署前端工程时, 若项目已 provision BaaS,
把 Supabase 连接信息写入前端 .env (VITE_SUPABASE_URL/ANON_KEY/SCHEMA)。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.artifact_deployer import PrototypeDeployer


def _make_app_code_content(*, backend_type: str = "supabase") -> dict:
    return {
        "project_dir": "generated/app",
        "build_status": "success",
        "backend_type": backend_type,
        "build_command": "npm run build",
        "artifact_path": "dist",
    }


class TestInjectSupabaseConfig:
    @pytest.mark.asyncio
    async def test_inject_writes_env_file(self, tmp_path):
        """项目已 provision BaaS + APP_CODE.backend_type=supabase → 写 .env。"""
        deployer = PrototypeDeployer.__new__(PrototypeDeployer)
        deployer._db = MagicMock()

        project = MagicMock()
        project.local_path = str(tmp_path)
        project.id = uuid.uuid4()

        # 前端工程目录
        app_dir = tmp_path / "generated" / "app"
        app_dir.mkdir(parents=True)

        baas_instance = MagicMock()
        baas_instance.schema_name = "arc_abc12345"
        baas_instance.supabase_url = "http://localhost:54321"

        todo = MagicMock()
        todo.id = uuid.uuid4()
        todo.project_id = project.id

        artifact = MagicMock()
        artifact.content = _make_app_code_content(backend_type="supabase")

        deployer._artifact_repo = MagicMock()

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.infrastructure.repositories.baas.BaasRepository"
        ) as MockBaasRepo, patch(
            "arc.config.settings"
        ) as mock_settings:
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            MockBaasRepo.return_value.get_by_project = AsyncMock(
                return_value=baas_instance
            )
            mock_settings.supabase_db_url = "postgresql://supabase@host/db"
            mock_settings.database_url = "postgresql://arc@localhost/arc"
            mock_settings.supabase_anon_key = "test-anon-key"
            mock_settings.supabase_api_url = "http://localhost:54321"

            # 跳过真实部署, 只测 env 注入
            with patch.object(
                deployer, "_deploy_project", new=AsyncMock()
            ):
                await deployer._maybe_inject_supabase_env(todo, artifact)

            env_file = app_dir / ".env"
            assert env_file.exists()
            content = env_file.read_text()
            assert "VITE_SUPABASE_URL" in content
            assert "http://localhost:54321" in content
            assert "VITE_SUPABASE_ANON_KEY" in content
            assert "arc_abc12345" in content
            assert "VITE_SUPABASE_SCHEMA" in content

    @pytest.mark.asyncio
    async def test_skip_when_no_baas_instance(self, tmp_path):
        """项目未 provision BaaS → 不写 env。"""
        deployer = PrototypeDeployer.__new__(PrototypeDeployer)
        deployer._db = MagicMock()

        project = MagicMock()
        project.local_path = str(tmp_path)
        project.id = uuid.uuid4()

        app_dir = tmp_path / "generated" / "app"
        app_dir.mkdir(parents=True)

        todo = MagicMock()
        todo.id = uuid.uuid4()
        todo.project_id = project.id

        artifact = MagicMock()
        artifact.content = _make_app_code_content(backend_type="supabase")

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.infrastructure.repositories.baas.BaasRepository"
        ) as MockBaasRepo:
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            MockBaasRepo.return_value.get_by_project = AsyncMock(return_value=None)

            await deployer._maybe_inject_supabase_env(todo, artifact)

            env_file = app_dir / ".env"
            assert not env_file.exists()

    @pytest.mark.asyncio
    async def test_skip_when_backend_not_supabase(self, tmp_path):
        """APP_CODE.backend_type != supabase → 不注入 (纯前端/外部后端不连 Arc BaaS)。"""
        deployer = PrototypeDeployer.__new__(PrototypeDeployer)
        deployer._db = MagicMock()

        project = MagicMock()
        project.local_path = str(tmp_path)
        project.id = uuid.uuid4()

        app_dir = tmp_path / "generated" / "app"
        app_dir.mkdir(parents=True)

        todo = MagicMock()
        todo.id = uuid.uuid4()
        todo.project_id = project.id

        artifact = MagicMock()
        artifact.content = _make_app_code_content(backend_type="none")

        with patch(
            "arc.infrastructure.repositories.baas.BaasRepository"
        ) as MockBaasRepo:
            MockBaasRepo.return_value.get_by_project = AsyncMock(return_value=MagicMock())

            await deployer._maybe_inject_supabase_env(todo, artifact)

            env_file = app_dir / ".env"
            assert not env_file.exists()

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self, tmp_path):
        """env 注入失败不阻断部署 (仅 warning)。"""
        deployer = PrototypeDeployer.__new__(PrototypeDeployer)
        deployer._db = MagicMock()

        todo = MagicMock()
        todo.id = uuid.uuid4()
        todo.project_id = uuid.uuid4()

        artifact = MagicMock()
        artifact.content = _make_app_code_content(backend_type="supabase")

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.infrastructure.repositories.baas.BaasRepository"
        ):
            MockProjRepo.return_value.get_by_id = AsyncMock(
                side_effect=Exception("db error")
            )

            # 不应抛错
            await deployer._maybe_inject_supabase_env(todo, artifact)

"""DeployService 单元测试 (v6.11 T5)。

覆盖编排逻辑, 不测 deployer/signer 外部客户端(在集成测试覆盖):
- 静态路由方法 _deploy_type_for / _detect_sign_targets
- rollback / list / get_latest 仓储编排
- deploy 主流程的失败补偿事务(异常→status=FAILED, 不留脏状态)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.deployment.service import DeployService
from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.signer import SignerType
from arc.domain.deployment.value_objects import DeploymentStatus, DeployType
from arc.domain.errors import AppError, NotFoundError
from arc.domain.project.value_objects import ProjectType


def _make_service() -> tuple[DeployService, MagicMock]:
    """构造 DeployService, 替换内部 repository 为 mock。"""
    db = MagicMock()
    db.commit = AsyncMock()
    svc = DeployService(db)
    svc._deploy_repo = MagicMock()
    svc._deploy_repo.get_by_id = AsyncMock()
    svc._deploy_repo.get_latest_by_version = AsyncMock()
    svc._deploy_repo.list_by_project = AsyncMock()
    svc._deploy_repo.update = AsyncMock()
    svc._deploy_repo.create = AsyncMock(side_effect=lambda d: d)
    svc._project_repo = MagicMock()
    svc._project_repo.get_by_id = AsyncMock()
    svc._project_repo.update = AsyncMock()
    svc._version_repo = MagicMock()
    svc._version_repo.get_by_id = AsyncMock()
    svc._version_repo.update = AsyncMock()
    return svc, db


class TestDeployTypeFor:
    def test_static_site(self):
        assert DeployService._deploy_type_for(ProjectType.STATIC_SITE) == DeployType.STATIC_SITE

    def test_binary_app(self):
        assert DeployService._deploy_type_for(ProjectType.BINARY_APP) == DeployType.BINARY_ARTIFACT

    def test_unsupported_raises(self):
        with pytest.raises(AppError, match="暂不支持"):
            DeployService._deploy_type_for("unknown_type")


class TestDetectSignTargets:
    def test_detects_app_exe_apk(self, tmp_path):
        (tmp_path / "MyApp.app").mkdir()
        (tmp_path / "setup.exe").write_text("x")
        (tmp_path / "app.apk").write_text("x")

        targets = DeployService._detect_sign_targets(str(tmp_path))
        signers = {t[0] for t in targets}
        assert SignerType.APPLE in signers
        assert SignerType.WINDOWS in signers
        assert SignerType.ANDROID in signers

    def test_empty_dir_returns_empty(self, tmp_path):
        assert DeployService._detect_sign_targets(str(tmp_path)) == []

    def test_nonexistent_dir_returns_empty(self):
        assert DeployService._detect_sign_targets("/nonexistent/path/xyz") == []

    def test_unsignable_extensions_ignored(self, tmp_path):
        # deb / AppImage / 无后缀 → 不签
        (tmp_path / "app.deb").write_text("x")
        (tmp_path / "app.AppImage").write_text("x")
        assert DeployService._detect_sign_targets(str(tmp_path)) == []

    def test_detects_msi_routes_to_windows(self, tmp_path):
        """v6.19 T4: .msi 扫描 → WINDOWS (经 EXTENSION_KIND→MSI→signer_for_kind 真相源, 取代扩展名硬编码)。"""
        (tmp_path / "Setup.msi").write_text("x")
        targets = DeployService._detect_sign_targets(str(tmp_path))
        signers = {t[0] for t in targets}
        assert SignerType.WINDOWS in signers

    def test_detects_ipa_hap_routes_to_ios_harmony(self, tmp_path):
        """v6.19 T7/T10 done: .ipa→IOS, .hap→HARMONY (KIND_SIGNER_TYPE 已回填, 取代 T5/T8 占位 None)。"""
        (tmp_path / "App.ipa").write_text("x")
        (tmp_path / "App.hap").write_text("x")
        targets = DeployService._detect_sign_targets(str(tmp_path))
        signers = {t[0] for t in targets}
        assert SignerType.IOS in signers
        assert SignerType.HARMONY in signers


class TestRollbackDeployment:
    async def test_success_transitions_to_rolled_back(self):
        svc, db = _make_service()
        deployment = Deployment(
            project_id=uuid.uuid4(), version_id=uuid.uuid4(),
            status=DeploymentStatus.DEPLOYED,
        )
        svc._deploy_repo.get_by_id = AsyncMock(return_value=deployment)

        result = await svc.rollback_deployment(uuid.uuid4())

        assert result.status == DeploymentStatus.ROLLED_BACK
        assert result is deployment
        svc._deploy_repo.update.assert_awaited_once_with(deployment)
        db.commit.assert_awaited_once()

    async def test_not_found_raises(self):
        svc, db = _make_service()
        svc._deploy_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError, match="不存在"):
            await svc.rollback_deployment(uuid.uuid4())


class TestListAndGet:
    async def test_list_deployments_passes_through(self):
        svc, db = _make_service()
        svc._deploy_repo.list_by_project = AsyncMock(return_value=[])

        result = await svc.list_deployments(uuid.uuid4())
        assert result == []
        svc._deploy_repo.list_by_project.assert_awaited_once()

    async def test_get_latest_returns_none_when_absent(self):
        svc, db = _make_service()
        svc._deploy_repo.get_latest_by_version = AsyncMock(return_value=None)

        assert await svc.get_latest_deployment(uuid.uuid4()) is None


class TestDeployFailureCompensation:
    async def test_exception_marks_failed_no_dirty_state(self):
        """deploy 主流程异常 → 补偿事务标记 FAILED, 不留 PENDING 脏状态。"""
        svc, db = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        with patch.object(
            svc, "_execute_deploy_steps", new_callable=AsyncMock,
            side_effect=RuntimeError("sandbox boom"),
        ):
            deployment = await svc.deploy(
                project_id=project_id, version_id=version_id,
                local_dir="/tmp/xyz", project_type=ProjectType.STATIC_SITE,
            )

        assert deployment.status == DeploymentStatus.FAILED
        assert "boom" in (deployment.error_message or "")
        svc._deploy_repo.update.assert_awaited()
        db.commit.assert_awaited_once()

    async def test_deploy_static_site_routes_to_deploy(self):
        """deploy_static_site 是薄封装, 应路由到 deploy(STATIC_SITE)。"""
        svc, db = _make_service()
        with patch.object(
            svc, "deploy", new_callable=AsyncMock,
        ) as mock_deploy:
            mock_deploy.return_value = MagicMock(status=DeploymentStatus.PENDING)
            await svc.deploy_static_site(
                project_id=uuid.uuid4(), version_id=uuid.uuid4(),
                local_dir="/tmp",
            )
            mock_deploy.assert_awaited_once()
            assert mock_deploy.call_args.kwargs["project_type"] == ProjectType.STATIC_SITE

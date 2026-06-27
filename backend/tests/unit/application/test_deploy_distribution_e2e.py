"""T6 端到端验证: 配凭证 → deploy BINARY_APP → distributor 上传 + manifest (v6.2.0 T6)。

mock 全部外部依赖 (db repo / deployer / signer / distributor / storage),
真实 DeployService.deploy() 串联 _sign → deployer → _distribute, 验证:
- BINARY_APP + project 触发 _distribute (distributor 链路 + manifest 持久化)
- STATIC_SITE 不触发 _distribute
满足版本验证标准: 配了凭证 → 签名后产物经商店上传。
"""

import uuid
from unittest.mock import AsyncMock

import pytest

from arc.application.deployment.service import DeployService
from arc.domain.deployment.distribution import (
    DistributionManifest,
    DistributionOutcome,
)
from arc.domain.deployment.distributor import DistributorType
from arc.domain.deployment.signer import SignerType, SignResult
from arc.domain.project.entity import Version
from arc.domain.project.value_objects import ProjectType
from arc.infrastructure.deployer.base import DeployResult


class _FakeDistSvc:
    """假 DistributionService: 记录 finalize, 返回预设 manifest。"""

    def __init__(self):
        self.finalize_called = False

    async def finalize(self, *a, **k):
        self.finalize_called = True
        return DistributionManifest(
            version_name="1.2.0",
            version_id="v",
            changelog="n",
            pub_date="2026-06-25T00:00:00Z",
            artifacts=(),
            distributions=(
                DistributionOutcome(
                    channel=DistributorType.TAURI_UPDATER,
                    uploaded=True,
                    store_url="https://up",
                ),
            ),
            download_page_url="https://cdn/p/d/download.html",
        )

    def generate_manifest_json(self, manifest):
        return '{"version_name":"1.2.0","download_page_url":"https://cdn/p/d/download.html"}'


class _MockDeployer:
    async def deploy(self, *, local_dir, project_id, deploy_id):
        return DeployResult(
            success=True, url="https://cdn/artifacts/p/d",
            prefix="artifacts/p/d", file_count=1,
        )


def _make_svc(version=None):
    """构造 DeployService, mock 所有 db repo + signer。"""
    db = AsyncMock()
    db.commit = AsyncMock()
    svc = DeployService(db=db)
    svc._deploy_repo.create = AsyncMock(side_effect=lambda d: d)
    svc._deploy_repo.update = AsyncMock(side_effect=lambda d: d)
    svc._version_repo.get_by_id = AsyncMock(return_value=version)
    svc._version_repo.update = AsyncMock()
    # 签名成功 (APPLE 产物 signed=True), 签名后产物经商店上传
    svc._sign_artifact = AsyncMock(
        return_value=[(SignerType.APPLE, "/tmp/App.dmg", SignResult(signed=True, signature_id="t"))]
    )
    return svc


class TestDeployFlowDistribute:
    @pytest.mark.asyncio
    async def test_binary_app_triggers_distribute_and_persists_manifest(
        self, monkeypatch, tmp_path
    ):
        """BINARY_APP + project → deploy 成功 + _distribute 触发 + manifest 持久化。"""
        version = Version(project_id=uuid.uuid4(), name="1.2.0")
        version.changelog = "release notes"
        svc = _make_svc(version=version)
        fake = _FakeDistSvc()
        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: fake
        )
        monkeypatch.setattr(
            "arc.application.deployment.service.get_deployer", lambda *a, **k: _MockDeployer()
        )

        result = await svc.deploy(
            project_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            local_dir=str(tmp_path),
            project_type=ProjectType.BINARY_APP,
            project=object(),
        )

        assert result.status.value == "deployed"
        assert fake.finalize_called is True  # _distribute 触发
        assert result.distribution_manifest != ""  # manifest 持久化
        assert "1.2.0" in result.distribution_manifest

    @pytest.mark.asyncio
    async def test_static_site_does_not_distribute(self, monkeypatch, tmp_path):
        """STATIC_SITE → deploy 成功但不触发 _distribute (分发只对 BINARY_APP)。"""
        version = Version(project_id=uuid.uuid4(), name="1.0.0")
        svc = _make_svc(version=version)
        fake = _FakeDistSvc()
        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: fake
        )
        monkeypatch.setattr(
            "arc.application.deployment.service.get_deployer", lambda *a, **k: _MockDeployer()
        )

        result = await svc.deploy(
            project_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            local_dir=str(tmp_path),
            project_type=ProjectType.STATIC_SITE,
            project=object(),
        )

        assert result.status.value == "deployed"
        assert fake.finalize_called is False
        assert result.distribution_manifest == ""

    @pytest.mark.asyncio
    async def test_distribute_failure_does_not_break_deploy(self, monkeypatch, tmp_path):
        """_distribute 抛异常 → deploy 仍成功 (graceful, 产物已在制品仓)。"""
        version = Version(project_id=uuid.uuid4(), name="1.2.0")
        svc = _make_svc(version=version)

        class _Boom:
            async def finalize(self, *a, **k):
                raise RuntimeError("distributor down")

            def generate_manifest_json(self, m):
                return ""

        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: _Boom()
        )
        monkeypatch.setattr(
            "arc.application.deployment.service.get_deployer", lambda *a, **k: _MockDeployer()
        )

        result = await svc.deploy(
            project_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
            local_dir=str(tmp_path),
            project_type=ProjectType.BINARY_APP,
            project=object(),
        )

        # 分发失败不阻断 deploy (产物已部署, 状态保持 deployed)
        assert result.status.value == "deployed"

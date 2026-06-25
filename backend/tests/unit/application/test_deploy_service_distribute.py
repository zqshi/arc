"""Tests for DeployService._distribute — 制品分发层接入 deploy 流程 (v6.2.0 T5)。

直接测 _distribute (mock version_repo + DistributionService), 不测整个 deploy 链路
(集成验证在 T6)。覆盖: manifest 持久化 + graceful 不阻断 + version 缺失跳过。
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
from arc.domain.deployment.entity import Deployment
from arc.domain.project.entity import Version


def _make_manifest():
    return DistributionManifest(
        version_name="1.2.0",
        version_id="v",
        changelog="n",
        pub_date="2026-06-25T00:00:00Z",
        artifacts=(),
        distributions=(
            DistributionOutcome(
                channel=DistributorType.TAURI_UPDATER, uploaded=True, store_url="https://up"
            ),
        ),
        download_page_url="https://cdn/p/d/download.html",
    )


class _FakeDistSvc:
    """假 DistributionService: 记录 finalize, 返回预设 manifest。"""

    def __init__(self):
        self.finalize_called = False

    async def finalize(self, *a, **k):
        self.finalize_called = True
        return _make_manifest()

    def generate_manifest_json(self, manifest):
        return '{"version_name": "1.2.0", "download_page_url": "https://cdn/p/d/download.html"}'


def _make_service(version=None):
    svc = DeployService(db=AsyncMock())
    svc._version_repo.get_by_id = AsyncMock(return_value=version)
    return svc


class TestDistribute:
    @pytest.mark.asyncio
    async def test_persists_manifest_when_version_exists(self, monkeypatch):
        version = Version(project_id=uuid.uuid4(), name="1.2.0")
        svc = _make_service(version=version)
        fake = _FakeDistSvc()
        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: fake
        )

        deployment = Deployment(project_id=uuid.uuid4(), version_id=uuid.uuid4())
        await svc._distribute(
            deployment, project=object(), version_id=uuid.uuid4(),
            local_dir="/tmp", sign_results=[], storage_prefix="p/d",
        )

        assert fake.finalize_called is True
        assert deployment.distribution_manifest != ""
        assert "1.2.0" in deployment.distribution_manifest

    @pytest.mark.asyncio
    async def test_graceful_on_exception_does_not_raise(self, monkeypatch):
        version = Version(project_id=uuid.uuid4(), name="1.2.0")
        svc = _make_service(version=version)

        class _Boom:
            async def finalize(self, *a, **k):
                raise RuntimeError("distributor down")

        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: _Boom()
        )

        deployment = Deployment(project_id=uuid.uuid4(), version_id=uuid.uuid4())
        # 不应抛异常 (分发失败不阻断 deploy)
        await svc._distribute(
            deployment, project=object(), version_id=uuid.uuid4(),
            local_dir="/tmp", sign_results=[], storage_prefix="p/d",
        )
        assert deployment.distribution_manifest == ""  # 未设

    @pytest.mark.asyncio
    async def test_skips_when_version_missing(self, monkeypatch):
        svc = _make_service(version=None)
        fake = _FakeDistSvc()
        monkeypatch.setattr(
            "arc.application.deployment.distribution.DistributionService", lambda: fake
        )

        deployment = Deployment(project_id=uuid.uuid4(), version_id=uuid.uuid4())
        await svc._distribute(
            deployment, project=object(), version_id=uuid.uuid4(),
            local_dir="/tmp", sign_results=[], storage_prefix="p/d",
        )
        assert fake.finalize_called is False
        assert deployment.distribution_manifest == ""

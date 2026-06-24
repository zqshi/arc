"""Tests for TauriUpdaterDistributor — Tauri 自建更新服务上传 (v6.2.0 T4)。

httpx PUT 上传产物到更新服务器。mock httpx, 真实上传需更新服务器 URL + secret。
"""

import pytest

from arc.domain.deployment.distributor import DistributorType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.distributor import load_distribution_creds_for_project
from arc.infrastructure.distributor.tauri_updater import TauriUpdaterDistributor

from cryptography.fernet import Fernet

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_tauri_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_distribution_creds(
        DistributorType.TAURI_UPDATER,
        {"tauri_updater_url": "https://update.example.com", "tauri_updater_secret": "secret-token"},
        encrypt,
    )
    return p


class TestTauriUpdaterGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_tauri_creds(self):
        """项目未配 Tauri updater 凭证 → skip。"""
        d = TauriUpdaterDistributor()
        project = Project(name="t")
        creds = load_distribution_creds_for_project(project, DistributorType.TAURI_UPDATER)
        result = await d.upload("/tmp/app.AppImage", signed=True, credentials=creds)
        assert result.uploaded is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (缺 secret) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.TAURI_UPDATER,
            {"tauri_updater_url": "https://u.example.com"},  # 缺 secret
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.TAURI_UPDATER)
        d = TauriUpdaterDistributor()
        result = await d.upload("/tmp/app.AppImage", signed=True, credentials=creds)
        assert result.skipped is True


class TestTauriUpdaterUpload:
    @pytest.mark.asyncio
    async def test_http_put_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → httpx PUT 上传产物 (mock httpx 验证请求)。"""
        artifact = tmp_path / "app.AppImage"
        artifact.write_bytes(b"fake-appimage")

        class _FakeResp:
            status_code = 200
            text = "uploaded"

        class _FakeClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.requests = []

            async def put(self, url, **kwargs):
                self.requests.append(("PUT", url, kwargs))
                return _FakeResp()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        fake_client = _FakeClient()
        monkeypatch.setattr("arc.infrastructure.distributor.tauri_updater.httpx.AsyncClient", lambda **kw: fake_client)
        project = _project_with_tauri_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.TAURI_UPDATER)

        d = TauriUpdaterDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is True
        assert result.store_url.startswith("https://update.example.com")
        # PUT 请求被发起, 含 auth header
        assert len(fake_client.requests) >= 1
        method, url, kw = fake_client.requests[0]
        assert method == "PUT"
        assert "update.example.com" in url

    @pytest.mark.asyncio
    async def test_upload_http_error_returns_fail(self, monkeypatch, tmp_path):
        """服务器返回非 2xx → fail。"""
        artifact = tmp_path / "app.AppImage"
        artifact.write_bytes(b"fake-appimage")

        class _FakeResp:
            status_code = 401
            text = "unauthorized"

        class _FakeClient:
            async def put(self, url, **kwargs):
                return _FakeResp()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr("arc.infrastructure.distributor.tauri_updater.httpx.AsyncClient", lambda **kw: _FakeClient())
        project = _project_with_tauri_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.TAURI_UPDATER)

        d = TauriUpdaterDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is False
        assert result.skipped is False
        assert "401" in result.error or "上传" in result.error


class TestTauriUpdaterType:
    def test_distributor_type(self):
        assert TauriUpdaterDistributor().distributor_type == DistributorType.TAURI_UPDATER

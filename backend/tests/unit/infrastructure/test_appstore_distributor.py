"""Tests for AppStoreDistributor — App Store Connect 上传 (v6.2.0 T2)。

用 xcrun altool --upload-app (CLI, 同 v6.1 AppleSigner subprocess 风格)。
mock subprocess, 真实上传需 App Store Connect API key + 网络。
"""

import pytest

from arc.domain.deployment.distributor import DistributorType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.distributor import load_distribution_creds_for_project
from arc.infrastructure.distributor.appstore import AppStoreDistributor

from cryptography.fernet import Fernet

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_appstore_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_distribution_creds(
        DistributorType.APP_STORE,
        {
            "appstore_issuer_id": "issuer-uuid",
            "appstore_key_id": "KEYID",
            "appstore_api_key": "-----PRIVATE KEY-----",
        },
        encrypt,
    )
    return p


class TestAppStoreDistributorGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_appstore_creds(self):
        """项目未配 App Store 凭证 → skip (产物落制品仓可手动下载)。"""
        d = AppStoreDistributor()
        project = Project(name="t")
        creds = load_distribution_creds_for_project(project, DistributorType.APP_STORE)
        result = await d.upload("/tmp/app.ipa", signed=True, credentials=creds)
        assert result.uploaded is False
        assert result.skipped is True
        assert "App Store" in result.error or "未配" in result.error

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (缺 api_key) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.APP_STORE,
            {"appstore_issuer_id": "uuid", "appstore_key_id": "KID"},  # 缺 api_key
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.APP_STORE)
        d = AppStoreDistributor()
        result = await d.upload("/tmp/app.ipa", signed=True, credentials=creds)
        assert result.skipped is True


class TestAppStoreDistributorUpload:
    @pytest.mark.asyncio
    async def test_altool_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → 调 xcrun altool --upload-app (mock 验证命令构造)。"""
        artifact = tmp_path / "App.ipa"
        artifact.write_bytes(b"fake-ipa")

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = "No errors uploading"
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_appstore_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.APP_STORE)

        d = AppStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is True
        altool_calls = [c for c in calls if "altool" in " ".join(c)]
        assert len(altool_calls) >= 1
        argv = altool_calls[0]
        assert "upload-app" in argv or "--upload-app" in argv
        assert "--apiKey" in argv
        key_idx = argv.index("--apiKey")
        assert argv[key_idx + 1] == "KEYID"

    @pytest.mark.asyncio
    async def test_upload_failure_returns_fail(self, monkeypatch, tmp_path):
        """altool 返回非零 → fail。"""
        artifact = tmp_path / "App.ipa"
        artifact.write_bytes(b"fake-ipa")

        def _fake_run(argv, **kwargs):

            class R:
                returncode = 1
                stdout = ""
                stderr = "altool: Error Description"
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_appstore_creds(monkeypatch)
        creds = load_distribution_creds_for_project(project, DistributorType.APP_STORE)

        d = AppStoreDistributor()
        result = await d.upload(str(artifact), signed=True, credentials=creds)

        assert result.uploaded is False
        assert result.skipped is False
        assert "altool" in result.error.lower() or "上传" in result.error


class TestAppStoreDistributorType:
    def test_distributor_type(self):
        assert AppStoreDistributor().distributor_type == DistributorType.APP_STORE

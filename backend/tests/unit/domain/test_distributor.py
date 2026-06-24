"""Tests for domain/deployment/distributor — 分发器抽象层 (v6.2.0 T1)。

分发是领域契约: "把签名后产物上传到商店/分发渠道"是领域行为, 具体实现
(App Store Connect / Play Console / Tauri updater) 在 infrastructure。
与 v6.1 Signer 同构 (domain 定义契约, infrastructure 实现)。

graceful skip 原则: 分发凭证未配 → skipped=True, 不阻断 (产物落制品仓可手动下载)。
"""

from arc.domain.deployment.distributor import (
    DistributeResult,
    DistributionCredentials,
    Distributor,
    DistributorType,
)


class TestDistributorType:
    def test_values(self):
        assert DistributorType.APP_STORE == "app_store"
        assert DistributorType.PLAY_STORE == "play_store"
        assert DistributorType.TAURI_UPDATER == "tauri_updater"


class TestDistributionCredentials:
    def test_empty_credentials(self):
        """未配任何分发凭证 → is_empty (触发 graceful skip)。"""
        creds = DistributionCredentials()
        assert creds.is_empty() is True

    def test_app_store_credentials(self):
        creds = DistributionCredentials(
            appstore_issuer_id="issuer-uuid",
            appstore_key_id="KEYID",
            appstore_api_key="-----BEGIN PRIVATE KEY-----...",
        )
        assert creds.has_app_store() is True
        assert creds.has_play_store() is False

    def test_play_store_credentials(self):
        """Play Console service account JSON (从 v6.1 SigningCredentials 归位)。"""
        creds = DistributionCredentials(play_key_json='{"type":"service_account"}')
        assert creds.has_play_store() is True

    def test_tauri_updater_credentials(self):
        creds = DistributionCredentials(
            tauri_updater_url="https://update.example.com",
            tauri_updater_secret="secret-token",
        )
        assert creds.has_tauri_updater() is True

    def test_frozen(self):
        creds = DistributionCredentials(play_key_json="x")
        try:
            creds.play_key_json = "y"  # type: ignore
            assert False, "应不可变"
        except Exception:
            pass


class TestDistributeResult:
    def test_uploaded_success(self):
        r = DistributeResult(uploaded=True, store_url="https://apps.apple.com/app/id123")
        assert r.uploaded is True
        assert r.skipped is False

    def test_graceful_skip(self):
        """凭证未配 → skipped, 产物落制品仓可手动下载。"""
        r = DistributeResult.skip(reason="APP_STORE 凭证未配置")
        assert r.uploaded is False
        assert r.skipped is True
        assert "未配置" in r.error

    def test_failure(self):
        r = DistributeResult.fail("upload failed: 401 unauthorized")
        assert r.uploaded is False
        assert r.skipped is False
        assert "401" in r.error


class TestDistributorInterface:
    def test_distributor_is_abstract(self):
        import pytest

        with pytest.raises(TypeError):
            Distributor()  # type: ignore[abstract]

    def test_concrete_distributor_implements_upload(self):
        class StubDistributor(Distributor):
            distributor_type = DistributorType.APP_STORE

            async def upload(self, artifact_path, signed, credentials):
                return DistributeResult(uploaded=True, store_url="stub")

        d = StubDistributor()
        assert d.distributor_type == DistributorType.APP_STORE

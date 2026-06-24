"""Tests for Project 实体分发凭证存取 (v6.2.0 T1)。

分发凭证按渠道分字段加密存储 (与签名凭证 v6.1 同构, 独立字段)。
加解密通过回调注入 (domain 不依赖 infrastructure/crypto)。
"""

from arc.domain.deployment.distributor import DistributorType
from arc.domain.project.entity import Project


def _encrypt_stub(plaintext: str) -> str:
    return f"ENC({plaintext})" if plaintext else ""


def _decrypt_stub(token: str) -> str:
    if token.startswith("ENC(") and token.endswith(")"):
        return token[4:-1]
    return ""


class TestProjectDistributionCreds:
    def test_set_and_get_app_store_creds(self):
        p = Project(name="t")
        creds = {"appstore_issuer_id": "uuid", "appstore_key_id": "KID", "appstore_api_key": "pk"}
        p.set_distribution_creds(DistributorType.APP_STORE, creds, _encrypt_stub)
        assert p.enc_appstore_creds.startswith("ENC(")
        assert p.get_distribution_creds(DistributorType.APP_STORE, _decrypt_stub) == creds

    def test_set_play_store_creds(self):
        p = Project(name="t")
        creds = {"play_key_json": '{"type":"service_account"}'}
        p.set_distribution_creds(DistributorType.PLAY_STORE, creds, _encrypt_stub)
        assert p.enc_playstore_creds.startswith("ENC(")
        assert p.get_distribution_creds(DistributorType.PLAY_STORE, _decrypt_stub) == creds

    def test_set_tauri_updater_creds(self):
        p = Project(name="t")
        creds = {"tauri_updater_url": "https://u.example.com", "tauri_updater_secret": "s"}
        p.set_distribution_creds(DistributorType.TAURI_UPDATER, creds, _encrypt_stub)
        assert p.enc_tauri_updater_creds.startswith("ENC(")
        assert p.get_distribution_creds(DistributorType.TAURI_UPDATER, _decrypt_stub) == creds

    def test_channel_isolation(self):
        """App Store 凭证不影响 Play/Tauri 字段。"""
        p = Project(name="t")
        p.set_distribution_creds(DistributorType.APP_STORE, {"appstore_issuer_id": "x"}, _encrypt_stub)
        assert p.enc_playstore_creds == ""
        assert p.enc_tauri_updater_creds == ""

    def test_get_unconfigured_returns_none(self):
        p = Project(name="t")
        assert p.get_distribution_creds(DistributorType.APP_STORE, _decrypt_stub) is None

    def test_empty_creds_not_stored(self):
        p = Project(name="t")
        p.set_distribution_creds(DistributorType.APP_STORE, {}, _encrypt_stub)
        assert p.enc_appstore_creds == ""

    def test_independent_from_signing_creds(self):
        """分发凭证与签名凭证字段独立 (v6.1 enc_apple_creds 不受分发影响)。"""
        from arc.domain.deployment.signer import SignerType

        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {"apple_dev_id": "x"}, _encrypt_stub)
        p.set_distribution_creds(DistributorType.APP_STORE, {"appstore_issuer_id": "y"}, _encrypt_stub)
        assert p.enc_apple_creds.startswith("ENC(")  # 签名凭证
        assert p.enc_appstore_creds.startswith("ENC(")  # 分发凭证 (独立字段)

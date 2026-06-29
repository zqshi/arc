"""Tests for infrastructure/signer 注册表 + 项目凭证加载 (v6.1.0)。

T2 后: AppleSigner 已注册, Windows/Android 未实现。
"""

from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SignerType, SigningCredentials
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.signer import SIGNERS, get_signer, load_credentials_for_project
from arc.infrastructure.signer.apple import AppleSigner

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


class TestLoadCredentialsForProject:
    def test_loads_apple_creds_from_project(self, monkeypatch):
        """凭证从项目解密加载 (项目维度, 非全局 config)。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.APPLE,
            {
                "apple_id": "dev@example.com",
                "apple_dev_id": "DEV123",
                "apple_team_id": "TEAM456",
                "apple_app_password": "abcd-1234-5678-efgh",
            },
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.APPLE)
        assert isinstance(creds, SigningCredentials)
        assert creds.has_apple() is True
        assert creds.apple_dev_id == "DEV123"
        assert creds.apple_id == "dev@example.com"

    def test_unconfigured_project_yields_empty(self):
        """项目未配该平台凭证 → 空 SigningCredentials (is_empty)。"""
        p = Project(name="t")
        creds = load_credentials_for_project(p, SignerType.APPLE)
        assert creds.is_empty() is True
        assert creds.has_apple() is False

    def test_platform_isolation(self, monkeypatch):
        """Apple 凭证不影响 Windows 加载。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {"apple_dev_id": "x"}, encrypt)
        win_creds = load_credentials_for_project(p, SignerType.WINDOWS)
        assert win_creds.is_empty() is True

    def test_loads_ios_creds_from_project(self, monkeypatch):
        """v6.19 T7: iOS 凭证从项目解密加载。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.IOS,
            {
                "ios_cert_path": "/certs/dev.p12",
                "ios_cert_password": "secret",
                "ios_identity": "iPhone Distribution: Team",
            },
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.IOS)
        assert isinstance(creds, SigningCredentials)
        assert creds.has_ios() is True
        assert creds.ios_identity == "iPhone Distribution: Team"

    def test_loads_harmony_creds_from_project(self, monkeypatch):
        """v6.19 T10: 鸿蒙凭证从项目解密加载。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.HARMONY,
            {
                "harmony_keystore_path": "/certs/dev.p12",
                "harmony_keystore_password": "secret",
                "harmony_key_alias": "release",
                "harmony_cert_path": "/certs/app.cer",
                "harmony_profile_path": "/certs/profile.p7b",
            },
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.HARMONY)
        assert isinstance(creds, SigningCredentials)
        assert creds.has_harmony() is True
        assert creds.harmony_key_alias == "release"


class TestGetSigner:
    def test_apple_registered(self):
        """T2 done: AppleSigner 已注册。"""
        signer = get_signer(SignerType.APPLE)
        assert signer is not None
        assert isinstance(signer, AppleSigner)

    def test_windows_registered(self):
        """T3 done: WindowsSigner 已注册。"""
        from arc.infrastructure.signer.windows import WindowsSigner

        signer = get_signer(SignerType.WINDOWS)
        assert signer is not None
        assert isinstance(signer, WindowsSigner)

    def test_android_registered(self):
        """T4 done: AndroidSigner 已注册。"""
        from arc.infrastructure.signer.android import AndroidSigner

        signer = get_signer(SignerType.ANDROID)
        assert signer is not None
        assert isinstance(signer, AndroidSigner)

    def test_ios_registered(self):
        """v6.19 T7 done: IosSigner 已注册。"""
        from arc.infrastructure.signer.ios import IosSigner

        signer = get_signer(SignerType.IOS)
        assert signer is not None
        assert isinstance(signer, IosSigner)

    def test_harmony_registered(self):
        """v6.19 T10 done: HarmonySigner 已注册。"""
        from arc.infrastructure.signer.harmony import HarmonySigner

        signer = get_signer(SignerType.HARMONY)
        assert signer is not None
        assert isinstance(signer, HarmonySigner)

    def test_all_platforms_registered(self):
        """五平台签名器全部注册 (v6.1 APPLE/WINDOWS/ANDROID + v6.19 IOS/HARMONY)。"""
        assert SignerType.APPLE in SIGNERS
        assert SignerType.WINDOWS in SIGNERS
        assert SignerType.ANDROID in SIGNERS
        assert SignerType.IOS in SIGNERS  # v6.19 T7
        assert SignerType.HARMONY in SIGNERS  # v6.19 T10

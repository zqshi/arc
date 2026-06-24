"""Tests for infrastructure/signer 注册表 + 项目凭证加载 (v6.1.0 T1 修正)。"""

from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SigningCredentials, SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import decrypt, encrypt
from arc.infrastructure.signer import SIGNERS, get_signer, load_credentials_for_project

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


class TestLoadCredentialsForProject:
    def test_loads_apple_creds_from_project(self, monkeypatch):
        """凭证从项目解密加载 (项目维度, 非全局 config)。用真实 crypto 存取。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.APPLE,
            {"apple_dev_id": "DEV123", "apple_team_id": "TEAM456"},
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.APPLE)
        assert isinstance(creds, SigningCredentials)
        assert creds.has_apple() is True
        assert creds.apple_dev_id == "DEV123"

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


class TestGetSigner:
    def test_unregistered_type_returns_none(self):
        """T2-T4 未实现时, get_signer 返回 None (调用方 graceful skip)。"""
        assert get_signer(SignerType.APPLE) is None
        assert get_signer(SignerType.WINDOWS) is None
        assert get_signer(SignerType.ANDROID) is None

    def test_signers_registry_starts_empty(self):
        """T1 阶段注册表为空, T2-T4 实现后填充。"""
        assert SIGNERS == {}

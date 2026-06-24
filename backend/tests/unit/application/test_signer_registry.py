"""Tests for infrastructure/signer 注册表 + 凭证加载 (v6.1.0 T1)。"""

from arc.config import settings
from arc.domain.deployment.signer import SigningCredentials, SignerType
from arc.infrastructure.signer import SIGNERS, get_signer, load_credentials


class TestLoadCredentials:
    def test_loads_from_settings(self):
        """凭证从 config.Settings 聚合加载。"""
        creds = load_credentials()
        assert isinstance(creds, SigningCredentials)
        # 默认 settings 全空 → is_empty
        assert creds.apple_dev_id == settings.apple_dev_id
        assert creds.play_key_json == settings.play_key_json

    def test_empty_settings_yields_empty_credentials(self):
        creds = load_credentials()
        # 默认 .env 未配凭证 → is_empty (CI/dev 环境)
        assert creds.is_empty() is True


class TestGetSigner:
    def test_unregistered_type_returns_none(self):
        """T2-T4 未实现时, get_signer 返回 None (调用方 graceful skip)。"""
        assert get_signer(SignerType.APPLE) is None
        assert get_signer(SignerType.WINDOWS) is None
        assert get_signer(SignerType.ANDROID) is None

    def test_signers_registry_starts_empty(self):
        """T1 阶段注册表为空, T2-T4 实现后填充。"""
        assert SIGNERS == {}

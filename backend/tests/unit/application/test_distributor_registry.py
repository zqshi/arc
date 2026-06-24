"""Tests for infrastructure/distributor 注册表 + 项目凭证加载 (v6.2.0 T1)。"""

from cryptography.fernet import Fernet

from arc.domain.deployment.distributor import DistributionCredentials, DistributorType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.distributor import (
    DISTRIBUTORS,
    get_distributor,
    load_distribution_creds_for_project,
)

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


class TestLoadDistributionCredsForProject:
    def test_loads_app_store_creds_from_project(self, monkeypatch):
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.APP_STORE,
            {"appstore_issuer_id": "uuid", "appstore_key_id": "KID", "appstore_api_key": "pk"},
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.APP_STORE)
        assert isinstance(creds, DistributionCredentials)
        assert creds.has_app_store() is True
        assert creds.appstore_issuer_id == "uuid"

    def test_loads_play_store_creds(self, monkeypatch):
        """play_key_json 归位到 DistributionCredentials (从 v6.1 SigningCredentials 迁出)。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(
            DistributorType.PLAY_STORE,
            {"play_key_json": '{"type":"service_account"}'},
            encrypt,
        )
        creds = load_distribution_creds_for_project(p, DistributorType.PLAY_STORE)
        assert creds.has_play_store() is True

    def test_unconfigured_project_yields_empty(self):
        p = Project(name="t")
        creds = load_distribution_creds_for_project(p, DistributorType.APP_STORE)
        assert creds.is_empty() is True

    def test_channel_isolation(self, monkeypatch):
        """App Store 凭证不影响 Tauri updater 加载。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_distribution_creds(DistributorType.APP_STORE, {"appstore_issuer_id": "x"}, encrypt)
        tauri_creds = load_distribution_creds_for_project(p, DistributorType.TAURI_UPDATER)
        assert tauri_creds.is_empty() is True


class TestGetDistributor:
    def test_unregistered_type_returns_none(self):
        """T2-T4 未实现时, get_distributor 返回 None (调用方 graceful skip)。"""
        assert get_distributor(DistributorType.APP_STORE) is None
        assert get_distributor(DistributorType.PLAY_STORE) is None
        assert get_distributor(DistributorType.TAURI_UPDATER) is None

    def test_distributors_registry_starts_empty(self):
        """T1 阶段注册表为空, T2-T4 实现后填充。"""
        assert DISTRIBUTORS == {}

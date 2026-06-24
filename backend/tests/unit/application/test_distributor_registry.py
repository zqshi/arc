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
    def test_appstore_registered(self):
        """T2 done: AppStoreDistributor 已注册。"""
        from arc.infrastructure.distributor.appstore import AppStoreDistributor

        d = get_distributor(DistributorType.APP_STORE)
        assert d is not None
        assert isinstance(d, AppStoreDistributor)

    def test_play_tauri_not_implemented(self):
        """T3/T4 未实现 → None (调用方 graceful skip)。"""
        assert get_distributor(DistributorType.PLAY_STORE) is None
        assert get_distributor(DistributorType.TAURI_UPDATER) is None

    def test_distributors_registry_has_appstore(self):
        """T2 后注册表含 APP_STORE; T3/T4 实现后补 PLAY/TAURI。"""
        assert DistributorType.APP_STORE in DISTRIBUTORS

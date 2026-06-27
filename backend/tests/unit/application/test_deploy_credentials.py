"""DeployService 凭证配置编排单元测试 (T2)。

验证 configure_signing_creds / configure_distribution_creds / list_credentials
正确编排 Project 实体行为 + 接通 infrastructure/crypto.encrypt。

application 层测试: mock repository (外部依赖), 不 mock domain (用真 Project)。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.distributor import DistributorType
from arc.domain.deployment.signer import SignerType
from arc.domain.errors import NotFoundError
from arc.domain.project.entity import Project


def _svc_with_mock_repo(project: Project | None) -> "DeployService":
    """构造绕过 __init__ 的 DeployService, mock 掉 project_repo。"""
    from arc.application.deployment.service import DeployService

    svc = DeployService.__new__(DeployService)
    svc._db = AsyncMock()
    svc._project_repo = AsyncMock()
    svc._project_repo.get_by_id = AsyncMock(return_value=project)
    svc._project_repo.update = AsyncMock()
    return svc


@pytest.fixture
def real_encryption(monkeypatch):
    """配置真实 Fernet 密钥, 让 encrypt/decrypt 真加解密 (非 identity 降级)。"""
    monkeypatch.setattr(
        "arc.config.settings.signing_secret_key", Fernet.generate_key().decode()
    )


class TestConfigureSigningCreds:
    @pytest.mark.asyncio
    async def test_persists_encrypted_not_plaintext(self, real_encryption):
        """configure 后 enc 字段非空且为密文 (非明文), update 被调用。"""
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)

        result = await svc.configure_signing_creds(
            uuid.uuid4(),
            SignerType.APPLE,
            {"apple_dev_id": "DEV123", "apple_team_id": "TEAM456",
             "apple_app_password": "secret-pass"},
            user_id=uuid.uuid4(),
        )

        assert result == {"platform": "apple", "configured": True}
        assert project.enc_apple_creds
        assert project.enc_apple_creds != ""  # 非空
        # 密文不应包含明文片段
        assert "DEV123" not in project.enc_apple_creds
        assert "secret-pass" not in project.enc_apple_creds
        svc._project_repo.update.assert_awaited_once_with(project)

    @pytest.mark.asyncio
    async def test_empty_creds_skips_storage(self, real_encryption):
        """空 dict 不存 (保持字段空), 不调 update。"""
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)

        await svc.configure_signing_creds(
            uuid.uuid4(), SignerType.APPLE, {}, user_id=uuid.uuid4()
        )

        assert project.enc_apple_creds == ""
        svc._project_repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_roundtrip_via_get(self, real_encryption):
        """configure 写入后 get_signing_creds 能解密读回原值 (set/get 闭环)。"""
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)
        creds = {"android_keystore_path": "/ks", "android_keystore_password": "p",
                "android_key_alias": "a", "android_key_password": "kp"}

        await svc.configure_signing_creds(
            uuid.uuid4(), SignerType.ANDROID, creds, user_id=uuid.uuid4()
        )

        from arc.infrastructure.crypto import decrypt
        read_back = project.get_signing_creds(SignerType.ANDROID, decrypt)
        assert read_back == creds

    @pytest.mark.asyncio
    async def test_project_not_found_raises(self, real_encryption):
        """project 不存在 (无权/不存在) → NotFoundError。"""
        svc = _svc_with_mock_repo(None)

        with pytest.raises(NotFoundError, match="not found|不存在|无权"):
            await svc.configure_signing_creds(
                uuid.uuid4(), SignerType.APPLE, {"apple_dev_id": "x"},
                user_id=uuid.uuid4(),
            )


class TestConfigureDistributionCreds:
    @pytest.mark.asyncio
    async def test_persists_distribution_creds(self, real_encryption):
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)

        result = await svc.configure_distribution_creds(
            uuid.uuid4(),
            DistributorType.PLAY_STORE,
            {"play_key_json": '{"type":"service_account"}',
             "play_package_name": "com.example.app"},
            user_id=uuid.uuid4(),
        )

        assert result == {"channel": "play_store", "configured": True}
        assert project.enc_playstore_creds
        assert "com.example.app" not in project.enc_playstore_creds

    @pytest.mark.asyncio
    async def test_distribution_independent_from_signing(self, real_encryption):
        """分发凭证字段独立于签名凭证字段 (互不影响)。"""
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)

        await svc.configure_distribution_creds(
            uuid.uuid4(), DistributorType.APP_STORE,
            {"appstore_issuer_id": "iss"}, user_id=uuid.uuid4()
        )

        assert project.enc_appstore_creds
        assert project.enc_apple_creds == ""  # 签名字段未受影响


class TestListCredentials:
    @pytest.mark.asyncio
    async def test_returns_configured_bool_masked(self, real_encryption):
        """list_credentials 返回各平台/渠道 configured bool, 不含明文。"""
        project = Project(name="t")
        svc = _svc_with_mock_repo(project)
        # 经 configure 写入 (真实路径), 再 list 读回
        await svc.configure_signing_creds(
            uuid.uuid4(), SignerType.APPLE,
            {"apple_dev_id": "DEV_SECRET_VALUE"}, user_id=uuid.uuid4(),
        )

        result = await svc.list_credentials(uuid.uuid4(), user_id=uuid.uuid4())

        assert result["signing"]["apple"] is True
        assert result["signing"]["windows"] is False
        assert result["signing"]["android"] is False
        assert result["distribution"]["app_store"] is False
        # 不含明文
        import json
        assert "DEV_SECRET_VALUE" not in json.dumps(result)

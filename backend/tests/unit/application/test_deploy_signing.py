"""Tests for DeployService._sign_artifact 路由修正 (v6.1.0 T5/T6)。

验证按产物平台(.app/.exe/.apk)选 signer, 而非 build_target 硬编码。
mock subprocess 验证签名链路激活。
"""

import pytest
from cryptography.fernet import Fernet

from arc.application.deployment.service import DeployService
from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _make_deploy_service():
    return DeployService.__new__(DeployService)


def _project_with_apple_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_signing_creds(
        SignerType.APPLE,
        {
            "apple_dev_id": "Developer ID Application: Test (TEAM123)",
            "apple_team_id": "TEAM123",
            "apple_app_password": "abcd-1234-5678-efgh",
        },
        encrypt,
    )
    return p


class TestSignArtifactRouting:
    @pytest.mark.asyncio
    async def test_app_product_routes_to_apple(self, monkeypatch, tmp_path):
        """.app 产物 → AppleSigner (mock codesign 验证激活)。local_dir 为产物父目录。"""
        app_dir = tmp_path / "MyApp.app"
        app_dir.mkdir()

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_apple_creds(monkeypatch)
        ds = _make_deploy_service()
        deployment = Deployment(
            project_id=project.id, version_id=project.id, deploy_type="binary_artifact"
        )
        # local_dir = tmp_path (产物父目录, 含 MyApp.app)
        await ds._sign_artifact(deployment, project, None, str(tmp_path))

        # AppleSigner 被调 (codesign), 签名目标是 MyApp.app
        codesign_calls = [c for c in calls if c and c[0] == "codesign"]
        assert len(codesign_calls) >= 1
        assert any("MyApp.app" in str(c) for c in codesign_calls)

    @pytest.mark.asyncio
    async def test_linux_bundle_not_signed(self, monkeypatch, tmp_path):
        """Linux deb/AppImage 产物 → 无签名器 (不签)。"""
        (tmp_path / "app_0.1.0_amd64.deb").write_text("fake deb")
        (tmp_path / "AppImage").write_text("fake appimage")

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_apple_creds(monkeypatch)
        ds = _make_deploy_service()
        deployment = Deployment(
            project_id=project.id, version_id=project.id, deploy_type="binary_artifact"
        )
        await ds._sign_artifact(deployment, project, None, str(tmp_path))

        # 无签名器被调 (deb/appimage 不签)
        assert calls == []

    @pytest.mark.asyncio
    async def test_unconfigured_creds_skips(self, monkeypatch, tmp_path):
        """.app 产物但项目未配 Apple 凭证 → graceful skip (不抛异常)。"""
        app_dir = tmp_path / "MyApp.app"
        app_dir.mkdir()

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = Project(name="t")  # 未配凭证
        ds = _make_deploy_service()
        deployment = Deployment(
            project_id=project.id, version_id=project.id, deploy_type="binary_artifact"
        )
        await ds._sign_artifact(deployment, project, None, str(tmp_path))

        # 凭证未配 → skip, 不调 codesign
        assert calls == []

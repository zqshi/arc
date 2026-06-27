"""Tests for AndroidSigner — apksigner (v6.1.0 T4)。

Android 签名用 app signing keystore (.jks), 非 Play 上传密钥 (play_key_json 留 v6.2 分发)。
mock subprocess (apksigner 需 Android SDK build-tools, 非 macOS 原生)。
"""

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.signer import load_credentials_for_project
from arc.infrastructure.signer.android import AndroidSigner

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_android_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_signing_creds(
        SignerType.ANDROID,
        {
            "android_keystore_path": "/keys/release.jks",
            "android_keystore_password": "ks-pass",
            "android_key_alias": "release-key",
            "android_key_password": "key-pass",
        },
        encrypt,
    )
    return p


class TestAndroidSignerGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_android_creds(self):
        """项目未配 Android 签名凭证 → skip。"""
        signer = AndroidSigner()
        project = Project(name="t")
        creds = load_credentials_for_project(project, SignerType.ANDROID)
        result = await signer.sign("/tmp/app.apk", creds)
        assert result.signed is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (缺 keystore_password) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.ANDROID,
            {"android_keystore_path": "/keys/release.jks", "android_key_alias": "k"},
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.ANDROID)
        signer = AndroidSigner()
        result = await signer.sign("/tmp/app.apk", creds)
        assert result.skipped is True


class TestAndroidSignerApksigner:
    @pytest.mark.asyncio
    async def test_apksigner_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → 调 apksigner sign (mock 验证命令构造)。"""
        artifact = tmp_path / "app.apk"
        artifact.write_bytes(b"fake-apk")

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_android_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.ANDROID)

        signer = AndroidSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        apksigner_calls = [c for c in calls if c and "apksigner" in c[0]]
        assert len(apksigner_calls) >= 1
        argv = apksigner_calls[0]
        assert "sign" in argv
        assert "--ks" in argv
        ks_idx = argv.index("--ks")
        assert "/keys/release.jks" in argv[ks_idx + 1]

    @pytest.mark.asyncio
    async def test_apksigner_failure_returns_fail(self, monkeypatch, tmp_path):
        """apksigner 返回非零 → fail。"""
        artifact = tmp_path / "app.apk"
        artifact.write_bytes(b"fake-apk")

        def _fake_run(argv, **kwargs):

            class R:
                returncode = 1
                stdout = ""
                stderr = "apksigner: keystore tampered"
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_android_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.ANDROID)

        signer = AndroidSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "apksigner" in result.error.lower() or "签名" in result.error


class TestAndroidSignerType:
    def test_signer_type(self):
        assert AndroidSigner().signer_type == SignerType.ANDROID

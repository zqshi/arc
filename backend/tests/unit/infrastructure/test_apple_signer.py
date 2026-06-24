"""Tests for AppleSigner — codesign + notarytool (v6.1.0 T2)。

mock subprocess, 不依赖真实 Apple Developer 证书/凭证。
真实签名验证需配凭证的项目 (手动, 标 slow)。
"""

import pytest

from arc.domain.deployment.signer import SignerType, SigningCredentials
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import decrypt, encrypt
from arc.infrastructure.signer import load_credentials_for_project
from arc.infrastructure.signer.apple import AppleSigner

from cryptography.fernet import Fernet

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _creds_with_apple(monkeypatch):
    """构造配了 Apple 凭证的项目。"""
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


class TestAppleSignerGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_apple_creds(self):
        """项目未配 Apple 凭证 → SignResult.skip (不调 codesign)。"""
        signer = AppleSigner()
        project = Project(name="t")  # 未配凭证
        creds = load_credentials_for_project(project, SignerType.APPLE)
        result = await signer.sign("/tmp/app.app", creds)
        assert result.signed is False
        assert result.skipped is True
        assert "Apple" in result.error or "未配" in result.error

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (只配 dev_id 缺 team_id) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {"apple_dev_id": "x"}, encrypt)  # 缺 team_id
        creds = load_credentials_for_project(p, SignerType.APPLE)
        signer = AppleSigner()
        result = await signer.sign("/tmp/app.app", creds)
        assert result.skipped is True


class TestAppleSignerCodesign:
    @pytest.mark.asyncio
    async def test_codesign_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → 调 codesign 签名 (mock subprocess 验证命令构造)。"""
        artifact = tmp_path / "App.app"
        artifact.mkdir()

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)
            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _creds_with_apple(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.APPLE)

        signer = AppleSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        # codesign 被调用, 命令含 --sign + identity (identity 作为 --sign 的下一个参数)
        codesign_calls = [c for c in calls if c and c[0] == "codesign"]
        assert len(codesign_calls) >= 1
        argv = codesign_calls[0]
        assert "--sign" in argv
        sign_idx = argv.index("--sign")
        assert "Developer ID Application" in argv[sign_idx + 1]

    @pytest.mark.asyncio
    async def test_codesign_failure_returns_fail(self, monkeypatch, tmp_path):
        """codesign 返回非零 → SignResult.fail (signed=False, skipped=False)。"""
        artifact = tmp_path / "App.app"
        artifact.mkdir()

        def _fake_run(argv, **kwargs):
            class R:
                returncode = 1
                stdout = ""
                stderr = "code signing failed: no identity"
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _creds_with_apple(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.APPLE)

        signer = AppleSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "failed" in result.error.lower() or "签名" in result.error


class TestAppleSignerNotarize:
    @pytest.mark.asyncio
    async def test_notarize_after_codesign(self, monkeypatch, tmp_path):
        """签名成功后提交 notarytool 公证 (mock 验证 xcrun notarytool 被调)。"""
        artifact = tmp_path / "App.app"
        artifact.mkdir()

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)
            class R:
                returncode = 0
                stdout = "" if argv[0] == "codesign" else "id: abc-123"
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _creds_with_apple(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.APPLE)

        signer = AppleSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        notary_calls = [c for c in calls if "notarytool" in c]
        assert len(notary_calls) >= 1


class TestAppleSignerType:
    def test_signer_type(self):
        assert AppleSigner().signer_type == SignerType.APPLE

"""Tests for IosSigner — security import + codesign (v6.19 T7)。

mock subprocess (security/codesign 非 macOS 原生, 真实验证需 macOS runner)。
镜像 test_windows_signer.py 结构。
"""

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.signer import load_credentials_for_project
from arc.infrastructure.signer.ios import IosSigner

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_ios_creds(monkeypatch):
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
    return p


class TestIosSignerGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_ios_creds(self):
        """项目未配 iOS 凭证 → skip。"""
        signer = IosSigner()
        project = Project(name="t")
        creds = load_credentials_for_project(project, SignerType.IOS)
        result = await signer.sign("/tmp/App.ipa", creds)
        assert result.signed is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (只配 cert_path 缺 password + identity) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(SignerType.IOS, {"ios_cert_path": "/c.p12"}, encrypt)
        creds = load_credentials_for_project(p, SignerType.IOS)
        signer = IosSigner()
        result = await signer.sign("/tmp/App.ipa", creds)
        assert result.skipped is True


class TestIosSignerCodesign:
    @pytest.mark.asyncio
    async def test_security_import_and_codesign_invoked(self, monkeypatch, tmp_path):
        """配齐凭证 → security import + codesign 两步 (mock 验证命令构造)。"""
        artifact = tmp_path / "App.ipa"
        artifact.write_text("binary")

        calls = []

        def _fake_run(argv, **kwargs):
            calls.append(argv)

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_ios_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.IOS)

        signer = IosSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        # 两步命令均被调
        security_calls = [c for c in calls if c and c[0] == "security"]
        codesign_calls = [c for c in calls if c and c[0] == "codesign"]
        assert len(security_calls) == 1
        assert len(codesign_calls) == 1
        # security import 构造
        sec = security_calls[0]
        assert "import" in sec
        assert "-P" in sec
        p_idx = sec.index("-P")
        assert sec[p_idx + 1] == "secret"
        assert "/certs/dev.p12" in sec
        # codesign 构造
        cs = codesign_calls[0]
        assert "--force" in cs
        assert "--sign" in cs
        sign_idx = cs.index("--sign")
        assert cs[sign_idx + 1] == "iPhone Distribution: Team"
        assert str(artifact) in cs

    @pytest.mark.asyncio
    async def test_security_import_failure_returns_fail(self, monkeypatch, tmp_path):
        """security import 返回非零 → fail (codesign 不执行)。"""
        artifact = tmp_path / "App.ipa"
        artifact.write_text("binary")

        def _fake_run(argv, **kwargs):
            if argv and argv[0] == "security":

                class R:
                    returncode = 1
                    stdout = ""
                    stderr = "security: Unix operation failed"
                return R()

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_ios_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.IOS)

        signer = IosSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "security import failed" in result.error.lower() or "security" in result.error

    @pytest.mark.asyncio
    async def test_codesign_failure_returns_fail(self, monkeypatch, tmp_path):
        """security import 成功但 codesign 失败 → fail。"""
        artifact = tmp_path / "App.ipa"
        artifact.write_text("binary")

        def _fake_run(argv, **kwargs):
            if argv and argv[0] == "codesign":

                class R:
                    returncode = 1
                    stdout = ""
                    stderr = "codesign: no identity found"
                return R()

            class R:
                returncode = 0
                stdout = ""
                stderr = ""
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_ios_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.IOS)

        signer = IosSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "codesign failed" in result.error.lower() or "codesign" in result.error


class TestIosSignerType:
    def test_signer_type(self):
        assert IosSigner().signer_type == SignerType.IOS

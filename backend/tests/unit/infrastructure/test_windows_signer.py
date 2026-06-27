"""Tests for WindowsSigner — signtool (v6.1.0 T3)。

mock subprocess (signtool 非 macOS 原生, 真实验证需 Windows)。
"""

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.signer import load_credentials_for_project
from arc.infrastructure.signer.windows import WindowsSigner

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_win_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_signing_creds(
        SignerType.WINDOWS,
        {"win_ev_cert_path": "/certs/ev.pfx", "win_ev_password": "secret"},
        encrypt,
    )
    return p


class TestWindowsSignerGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_win_creds(self):
        """项目未配 Windows 凭证 → skip。"""
        signer = WindowsSigner()
        project = Project(name="t")
        creds = load_credentials_for_project(project, SignerType.WINDOWS)
        result = await signer.sign("/tmp/app.exe", creds)
        assert result.signed is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (只配 cert_path 缺 password) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(SignerType.WINDOWS, {"win_ev_cert_path": "/c.pfx"}, encrypt)
        creds = load_credentials_for_project(p, SignerType.WINDOWS)
        signer = WindowsSigner()
        result = await signer.sign("/tmp/app.exe", creds)
        assert result.skipped is True


class TestWindowsSignerSigntool:
    @pytest.mark.asyncio
    async def test_signtool_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配了凭证 → 调 signtool sign (mock 验证命令构造)。"""
        artifact = tmp_path / "App.exe"
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
        project = _project_with_win_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.WINDOWS)

        signer = WindowsSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        signtool_calls = [c for c in calls if c and "signtool" in c[0]]
        assert len(signtool_calls) >= 1
        argv = signtool_calls[0]
        assert "sign" in argv
        assert "/f" in argv  # cert file flag
        cert_idx = argv.index("/f")
        assert "/certs/ev.pfx" in argv[cert_idx + 1]

    @pytest.mark.asyncio
    async def test_signtool_failure_returns_fail(self, monkeypatch, tmp_path):
        """signtool 返回非零 → fail。"""
        artifact = tmp_path / "App.exe"
        artifact.write_text("binary")

        def _fake_run(argv, **kwargs):

            class R:
                returncode = 1
                stdout = ""
                stderr = "signtool: no certificate found"
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_win_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.WINDOWS)

        signer = WindowsSigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "signtool" in result.error.lower() or "签名" in result.error


class TestWindowsSignerType:
    def test_signer_type(self):
        assert WindowsSigner().signer_type == SignerType.WINDOWS

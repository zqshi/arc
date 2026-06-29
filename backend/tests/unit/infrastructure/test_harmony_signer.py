"""Tests for HarmonySigner — hap-sign-tool sign-app (v6.19 T10)。

mock subprocess (hap-sign-tool 是华为 DevEco 工具, 非 macOS/Linux 原生)。
镜像 test_windows_signer.py 结构 (单命令签名器)。
"""

import pytest
from cryptography.fernet import Fernet

from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project
from arc.infrastructure.crypto import encrypt
from arc.infrastructure.signer import load_credentials_for_project
from arc.infrastructure.signer.harmony import HarmonySigner

_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


def _project_with_harmony_creds(monkeypatch):
    monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
    p = Project(name="t")
    p.set_signing_creds(
        SignerType.HARMONY,
        {
            "harmony_keystore_path": "/certs/dev.p12",
            "harmony_keystore_password": "secret",
            "harmony_key_alias": "release",
            "harmony_cert_path": "/certs/app.cer",
            "harmony_profile_path": "/certs/profile.p7b",
        },
        encrypt,
    )
    return p


class TestHarmonySignerGracefulSkip:
    @pytest.mark.asyncio
    async def test_skip_when_no_harmony_creds(self):
        """项目未配鸿蒙凭证 → skip。"""
        signer = HarmonySigner()
        project = Project(name="t")
        creds = load_credentials_for_project(project, SignerType.HARMONY)
        result = await signer.sign("/tmp/App.hap", creds)
        assert result.signed is False
        assert result.skipped is True

    @pytest.mark.asyncio
    async def test_skip_when_partial_creds(self, monkeypatch):
        """凭证不完整 (缺 cert_path + profile_path) → skip。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        p = Project(name="t")
        p.set_signing_creds(
            SignerType.HARMONY,
            {"harmony_keystore_path": "/c.p12", "harmony_keystore_password": "p"},
            encrypt,
        )
        creds = load_credentials_for_project(p, SignerType.HARMONY)
        signer = HarmonySigner()
        result = await signer.sign("/tmp/App.hap", creds)
        assert result.skipped is True


class TestHarmonySignerHapSignTool:
    @pytest.mark.asyncio
    async def test_hap_sign_tool_invoked_when_creds_present(self, monkeypatch, tmp_path):
        """配齐凭证 → 调 hap-sign-tool sign-app (mock 验证命令构造)。"""
        artifact = tmp_path / "App.hap"
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
        project = _project_with_harmony_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.HARMONY)

        signer = HarmonySigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is True
        hap_calls = [c for c in calls if c and "hap-sign-tool" in c[0]]
        assert len(hap_calls) == 1
        argv = hap_calls[0]
        assert "sign-app" in argv
        assert "-keyAlias" in argv
        alias_idx = argv.index("-keyAlias")
        assert argv[alias_idx + 1] == "release"
        assert "-appCertFile" in argv
        cer_idx = argv.index("-appCertFile")
        assert argv[cer_idx + 1] == "/certs/app.cer"
        assert "-profileFile" in argv
        prof_idx = argv.index("-profileFile")
        assert argv[prof_idx + 1] == "/certs/profile.p7b"
        assert "-inFile" in argv
        assert "-keystoreFile" in argv
        assert str(artifact) in argv

    @pytest.mark.asyncio
    async def test_hap_sign_tool_failure_returns_fail(self, monkeypatch, tmp_path):
        """hap-sign-tool 返回非零 → fail。"""
        artifact = tmp_path / "App.hap"
        artifact.write_text("binary")

        def _fake_run(argv, **kwargs):

            class R:
                returncode = 1
                stdout = ""
                stderr = "hap-sign-tool: keystore password incorrect"
            return R()

        monkeypatch.setattr("arc.infrastructure.signer._cmd.subprocess.run", _fake_run)
        project = _project_with_harmony_creds(monkeypatch)
        creds = load_credentials_for_project(project, SignerType.HARMONY)

        signer = HarmonySigner()
        result = await signer.sign(str(artifact), creds)

        assert result.signed is False
        assert result.skipped is False
        assert "hap-sign-tool failed" in result.error.lower() or "hap-sign-tool" in result.error


class TestHarmonySignerType:
    def test_signer_type(self):
        assert HarmonySigner().signer_type == SignerType.HARMONY

"""Tests for domain/deployment/signer — 签名器抽象层 (v6.1.0 T1)。

签名是领域契约: "对构建产物加签"是领域行为, 具体实现(codesign/signtool/apksigner)
在 infrastructure。Signer 接口 + 值对象在 domain, 与 repository 接口同构。

graceful skip 原则: 凭证未配 → skipped=True, 构建不阻断 (仅 warning)。
"""

from arc.domain.deployment.signer import (
    Signer,
    SignerType,
    SigningCredentials,
    SignResult,
)


class TestSignerType:
    def test_values(self):
        assert SignerType.APPLE == "apple"
        assert SignerType.WINDOWS == "windows"
        assert SignerType.ANDROID == "android"


class TestSigningCredentials:
    def test_empty_credentials(self):
        """未配任何凭证 → is_empty=True (触发 graceful skip)。"""
        creds = SigningCredentials()
        assert creds.is_empty() is True

    def test_apple_credentials(self):
        creds = SigningCredentials(
            apple_dev_id="DEV123", apple_team_id="TEAM456", apple_app_password="xxxx-xxxx-xxxx-xxxx"
        )
        assert creds.is_empty() is False
        assert creds.has_apple() is True
        assert creds.has_windows() is False

    def test_apple_partial_creds_not_complete(self):
        """缺 app_password → has_apple False (notarize 无法提交)。"""
        creds = SigningCredentials(apple_dev_id="DEV123", apple_team_id="TEAM456")
        assert creds.has_apple() is False

    def test_windows_credentials(self):
        creds = SigningCredentials(
            win_ev_cert_path="/certs/ev.pfx", win_ev_password="secret"
        )
        assert creds.has_windows() is True
        assert creds.has_apple() is False

    def test_android_credentials(self):
        """Android 签名用 app signing keystore (非 Play 上传密钥)。"""
        creds = SigningCredentials(
            android_keystore_path="/keys/release.jks",
            android_keystore_password="ks-pass",
            android_key_alias="release-key",
        )
        assert creds.has_android() is True

    def test_play_key_json_not_in_signing_credentials(self):
        """play_key_json 归位到 DistributionCredentials (v6.2), 不在 SigningCredentials。"""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(SigningCredentials)}
        assert "play_key_json" not in field_names

    def test_frozen(self):
        creds = SigningCredentials(apple_dev_id="x")
        try:
            creds.apple_dev_id = "y"  # type: ignore
            assert False, "应不可变"
        except Exception:
            pass


class TestSignResult:
    def test_signed_success(self):
        r = SignResult(signed=True, signature_id="abc", signed_path="/p/app.deb")
        assert r.signed is True
        assert r.skipped is False

    def test_graceful_skip(self):
        """凭证未配 → skipped=True, signed=False, 不阻断。"""
        r = SignResult.skip(reason="APPLE_DEV_ID 未配置")
        assert r.signed is False
        assert r.skipped is True
        assert "未配置" in r.error

    def test_failure(self):
        r = SignResult.fail("codesign 执行失败")
        assert r.signed is False
        assert r.skipped is False
        assert "失败" in r.error


class TestSignerInterface:
    def test_signer_is_abstract(self):
        """Signer 不可实例化 (ABC)。"""
        import pytest

        with pytest.raises(TypeError):
            Signer()  # type: ignore[abstract]

    def test_concrete_signer_implements_sign(self):
        """子类必须实现 sign。"""

        class StubSigner(Signer):
            signer_type = SignerType.APPLE

            async def sign(self, artifact_path, credentials):
                return SignResult(signed=True, signature_id="stub")

        s = StubSigner()
        assert s.signer_type == SignerType.APPLE

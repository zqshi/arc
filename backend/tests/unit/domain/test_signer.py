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
        assert SignerType.IOS == "ios"  # v6.19 T7
        assert SignerType.HARMONY == "harmony"  # v6.19 T10


class TestSigningCredentials:
    def test_empty_credentials(self):
        """未配任何凭证 → is_empty=True (触发 graceful skip)。"""
        creds = SigningCredentials()
        assert creds.is_empty() is True

    def test_apple_credentials(self):
        creds = SigningCredentials(
            apple_id="dev@example.com",
            apple_dev_id="DEV123", apple_team_id="TEAM456", apple_app_password="xxxx-xxxx-xxxx-xxxx"
        )
        assert creds.is_empty() is False
        assert creds.has_apple() is True
        assert creds.has_windows() is False

    def test_apple_partial_creds_not_complete(self):
        """缺 app_password → has_apple False (notarize 无法提交)。"""
        creds = SigningCredentials(
            apple_id="dev@example.com", apple_dev_id="DEV123", apple_team_id="TEAM456"
        )
        assert creds.has_apple() is False

    def test_apple_missing_id_not_complete(self):
        """v6.13 P3: 缺 apple_id (邮箱) → has_apple False (notarytool --apple-id 无法提交)。"""
        creds = SigningCredentials(
            apple_dev_id="DEV123", apple_team_id="TEAM456", apple_app_password="xxxx-xxxx-xxxx-xxxx"
        )
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

    def test_ios_credentials(self):
        """v6.19 T7: iOS 签名 (security import + codesign) 需 cert + password + identity。"""
        creds = SigningCredentials(
            ios_cert_path="/certs/dev.p12",
            ios_cert_password="secret",
            ios_identity="iPhone Distribution: Team",
        )
        assert creds.has_ios() is True
        assert creds.is_empty() is False

    def test_ios_partial_creds_not_complete(self):
        """缺 identity → has_ios False (codesign --sign 无目标)。"""
        creds = SigningCredentials(
            ios_cert_path="/certs/dev.p12", ios_cert_password="secret"
        )
        assert creds.has_ios() is False

    def test_ios_profile_not_required_for_has(self):
        """provisioning_profile 缺失不影响 has_ios (codesign 可执行, profile 属分发关注)。"""
        creds = SigningCredentials(
            ios_cert_path="/c.p12", ios_cert_password="p", ios_identity="id"
        )
        assert creds.has_ios() is True

    def test_harmony_credentials(self):
        """v6.19 T10: 鸿蒙签名 (hap-sign-tool) 需 keystore + alias + cer + profile。"""
        creds = SigningCredentials(
            harmony_keystore_path="/certs/dev.p12",
            harmony_keystore_password="secret",
            harmony_key_alias="release",
            harmony_cert_path="/certs/app.cer",
            harmony_profile_path="/certs/profile.p7b",
        )
        assert creds.has_harmony() is True
        assert creds.is_empty() is False

    def test_harmony_partial_creds_not_complete(self):
        """缺 profile_path → has_harmony False (hap-sign-tool profileFile 必需)。"""
        creds = SigningCredentials(
            harmony_keystore_path="/c.p12",
            harmony_keystore_password="p",
            harmony_key_alias="a",
            harmony_cert_path="/c.cer",
        )
        assert creds.has_harmony() is False

    def test_harmony_key_password_not_required_for_has(self):
        """key_password 缺失不影响 has_harmony (签名器用 keystore_password 兜底)。"""
        creds = SigningCredentials(
            harmony_keystore_path="/c.p12",
            harmony_keystore_password="p",
            harmony_key_alias="a",
            harmony_cert_path="/c.cer",
            harmony_profile_path="/c.p7b",
        )
        assert creds.has_harmony() is True

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

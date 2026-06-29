"""Tests for Project 实体签名凭证存取 (v6.1.0 T1 修正)。

凭证按平台分字段加密存储。加解密通过回调注入 (domain 不依赖 infrastructure/crypto),
避免 domain→infrastructure 违规。
"""

from arc.domain.deployment.signer import SignerType
from arc.domain.project.entity import Project


# 加解密 stub: 简单异或模拟加密 (测试不依赖真实 Fernet)
def _encrypt_stub(plaintext: str) -> str:
    return f"ENC({plaintext})" if plaintext else ""


def _decrypt_stub(token: str) -> str:
    if token.startswith("ENC(") and token.endswith(")"):
        return token[4:-1]
    return ""


class TestProjectSigningCreds:
    def test_set_and_get_apple_creds(self):
        """存 Apple 凭证后能解密取回。"""
        p = Project(name="t")
        creds = {"apple_dev_id": "DEV123", "apple_team_id": "TEAM456"}
        p.set_signing_creds(SignerType.APPLE, creds, _encrypt_stub)
        assert p.enc_apple_creds.startswith("ENC(")  # 已加密 (不依赖具体序列化格式)
        got = p.get_signing_creds(SignerType.APPLE, _decrypt_stub)
        assert got == creds

    def test_platform_isolation(self):
        """Apple 凭证不影响 Windows/Android/iOS/鸿蒙 字段。"""
        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {"apple_dev_id": "x"}, _encrypt_stub)
        assert p.enc_win_creds == ""
        assert p.enc_android_creds == ""
        assert p.enc_ios_creds == ""  # v6.19 T7
        assert p.enc_harmony_creds == ""  # v6.19 T10

    def test_get_unconfigured_returns_none(self):
        """未配凭证的平台 → get 返回 None。"""
        p = Project(name="t")
        assert p.get_signing_creds(SignerType.APPLE, _decrypt_stub) is None
        assert p.get_signing_creds(SignerType.WINDOWS, _decrypt_stub) is None
        assert p.get_signing_creds(SignerType.IOS, _decrypt_stub) is None  # v6.19 T7
        assert p.get_signing_creds(SignerType.HARMONY, _decrypt_stub) is None  # v6.19 T10

    def test_set_windows_creds(self):
        p = Project(name="t")
        creds = {"win_ev_cert_path": "/c.pfx", "win_ev_password": "pw"}
        p.set_signing_creds(SignerType.WINDOWS, creds, _encrypt_stub)
        assert p.enc_win_creds.startswith("ENC(")
        assert p.get_signing_creds(SignerType.WINDOWS, _decrypt_stub) == creds

    def test_set_android_creds(self):
        p = Project(name="t")
        creds = {"android_keystore_path": "/keys/release.jks", "android_keystore_password": "pw"}
        p.set_signing_creds(SignerType.ANDROID, creds, _encrypt_stub)
        assert p.enc_android_creds.startswith("ENC(")
        assert p.get_signing_creds(SignerType.ANDROID, _decrypt_stub) == creds

    def test_set_and_get_ios_creds(self):
        """v6.19 T7: iOS 凭证存取 round-trip (enc_ios_creds 字段)。"""
        p = Project(name="t")
        creds = {
            "ios_cert_path": "/certs/dev.p12",
            "ios_cert_password": "secret",
            "ios_identity": "iPhone Distribution: Team",
        }
        p.set_signing_creds(SignerType.IOS, creds, _encrypt_stub)
        assert p.enc_ios_creds.startswith("ENC(")
        assert p.get_signing_creds(SignerType.IOS, _decrypt_stub) == creds

    def test_set_and_get_harmony_creds(self):
        """v6.19 T10: 鸿蒙凭证存取 round-trip (enc_harmony_creds 字段)。"""
        p = Project(name="t")
        creds = {
            "harmony_keystore_path": "/certs/dev.p12",
            "harmony_keystore_password": "secret",
            "harmony_key_alias": "release",
            "harmony_cert_path": "/certs/app.cer",
            "harmony_profile_path": "/certs/profile.p7b",
        }
        p.set_signing_creds(SignerType.HARMONY, creds, _encrypt_stub)
        assert p.enc_harmony_creds.startswith("ENC(")
        assert p.get_signing_creds(SignerType.HARMONY, _decrypt_stub) == creds

    def test_overwrite_creds(self):
        """重复 set 覆盖旧凭证。"""
        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {"a": "1"}, _encrypt_stub)
        p.set_signing_creds(SignerType.APPLE, {"a": "2"}, _encrypt_stub)
        assert p.get_signing_creds(SignerType.APPLE, _decrypt_stub) == {"a": "2"}

    def test_empty_creds_not_stored(self):
        """空 dict → 不存 (enc 字段保持空)。"""
        p = Project(name="t")
        p.set_signing_creds(SignerType.APPLE, {}, _encrypt_stub)
        assert p.enc_apple_creds == ""

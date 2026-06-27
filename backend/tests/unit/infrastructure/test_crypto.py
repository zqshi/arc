"""Tests for infrastructure/crypto — Fernet 对称加密工具 (v6.1.0)。"""

from cryptography.fernet import Fernet

from arc.infrastructure.crypto import _fernet, decrypt, encrypt

# 测试用固定密钥 (不依赖 env 是否配 signing_secret_key)
_TEST_KEY = Fernet.generate_key().decode()


class _SettingsWithKey:
    signing_secret_key = _TEST_KEY


class TestEncryptDecrypt:
    def test_roundtrip(self, monkeypatch):
        """加密后解密还原原文 (注入测试密钥)。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        original = "apple_dev_id=ABCDE12345;team_id=TEAM67890"
        token = encrypt(original)
        assert token != original  # 确实加密了
        assert decrypt(token) == original

    def test_empty_input_encrypt(self):
        """空字符串加密 → 空字符串 (不产生空 token)。"""
        assert encrypt("") == ""

    def test_empty_input_decrypt(self):
        """空 token 解密 → 空字符串。"""
        assert decrypt("") == ""

    def test_decrypt_invalid_token_returns_empty(self, monkeypatch):
        """非法 token 解密 → 空串 (不抛异常, 调用方按未配凭证处理)。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        assert decrypt("not-a-valid-fernet-token") == ""

    def test_unicode_roundtrip(self, monkeypatch):
        """含中文/特殊字符的凭证往返。"""
        monkeypatch.setattr("arc.infrastructure.crypto.settings", _SettingsWithKey())
        original = "凭证=中文测试🔑"
        assert decrypt(encrypt(original)) == original


class TestEmptyKeyFallback:
    """空密钥降级 identity (dev 环境, 不阻断启动)。"""

    def test_no_fernet_when_key_empty(self, monkeypatch):
        """signing_secret_key 未配 → _fernet() 返回 None, 加解密退化为 identity。"""
        monkeypatch.setattr(
            "arc.infrastructure.crypto.settings",
            type("S", (), {"signing_secret_key": ""})(),
        )
        assert _fernet() is None
        assert encrypt("x") == "x"  # identity
        assert decrypt("x") == "x"


"""domain/llm 实体行为单元测试 (v6.20 L1)。

零 mock, 直接构造实体, 验证加解密注入式 + 状态变更 + repr 防泄露。
"""
from __future__ import annotations

import uuid

import pytest

from arc.domain.llm.entity import LLMProvider
from arc.domain.llm.value_objects import LLMProviderKind


# 加解密函数 (测试用 identity, 模拟 Fernet 加解密行为)
def _identity_encrypt(plaintext: str) -> str:
    return f"enc({plaintext})"


def _identity_decrypt(token: str) -> str:
    if token.startswith("enc(") and token.endswith(")"):
        return token[4:-1]
    return ""


class TestLLMProviderCreation:
    def test_defaults(self) -> None:
        p = LLMProvider(
            user_id=uuid.uuid4(),
            name="我的OpenAI",
            kind=LLMProviderKind.OPENAI_COMPATIBLE,
            base_url="https://api.openai.com/v1",
        )
        assert p.id is not None
        assert p.api_key_enc == ""
        assert p.models == []
        assert p.is_default is False
        assert p.has_api_key() is False
        assert p.created_at is not None

    def test_full_fields(self) -> None:
        p = LLMProvider(
            user_id=uuid.uuid4(),
            name="本地ollama",
            kind=LLMProviderKind.OPENAI_COMPATIBLE,
            base_url="http://localhost:11434/v1",
            api_key_enc="enc(token)",
            models=["llama3", "qwen"],
            is_default=True,
        )
        assert p.name == "本地ollama"
        assert p.has_api_key() is True
        assert p.models == ["llama3", "qwen"]
        assert p.is_default is True


class TestApiKeyEncryption:
    def test_set_api_key_encrypts(self) -> None:
        p = _make_provider()
        p.set_api_key("sk-secret", _identity_encrypt)
        assert p.api_key_enc == "enc(sk-secret)"
        assert p.has_api_key() is True

    def test_set_empty_api_key_clears(self) -> None:
        p = _make_provider(api_key_enc="enc(old)")
        p.set_api_key("", _identity_encrypt)
        assert p.api_key_enc == ""
        assert p.has_api_key() is False

    def test_get_api_key_decrypts(self) -> None:
        p = _make_provider()
        p.set_api_key("sk-secret", _identity_encrypt)
        assert p.get_api_key(_identity_decrypt) == "sk-secret"

    def test_get_api_key_empty_when_unset(self) -> None:
        p = _make_provider()
        assert p.get_api_key(_identity_decrypt) == ""

    def test_roundtrip_preserves_key(self) -> None:
        p = _make_provider(kind=LLMProviderKind.ANTHROPIC)
        p.set_api_key("sk-abc-123", _identity_encrypt)
        assert p.get_api_key(_identity_decrypt) == "sk-abc-123"


class TestLLMProviderBehavior:
    def test_set_models(self) -> None:
        p = _make_provider()
        p.set_models(["gpt-4o", "gpt-4o-mini"])
        assert p.models == ["gpt-4o", "gpt-4o-mini"]

    def test_set_models_copies_list(self) -> None:
        p = _make_provider()
        src = ["a", "b"]
        p.set_models(src)
        src.append("c")
        assert p.models == ["a", "b"]  # 不被外部修改影响

    def test_mark_default(self) -> None:
        p = _make_provider()
        assert p.is_default is False
        p.mark_default()
        assert p.is_default is True

    def test_clear_default(self) -> None:
        p = _make_provider(is_default=True)
        p.clear_default()
        assert p.is_default is False

    def test_rename(self) -> None:
        p = _make_provider(name="old")
        p.rename("new name")
        assert p.name == "new name"

    def test_rename_empty_raises(self) -> None:
        p = _make_provider(name="old")
        with pytest.raises(ValueError):
            p.rename("")

    def test_update_endpoint(self) -> None:
        p = _make_provider(base_url="https://old/v1")
        p.update_endpoint("https://new/v1")
        assert p.base_url == "https://new/v1"


class TestReprSafety:
    def test_api_key_not_leaked_in_repr(self) -> None:
        """repr 隐藏 api_key_enc 字段, 防止日志/异常泄露密钥。"""
        p = _make_provider()
        p.set_api_key("sk-super-secret", _identity_encrypt)
        repr_str = repr(p)
        assert "sk-super-secret" not in repr_str
        assert "api_key_enc" not in repr_str


def _make_provider(
    *,
    name: str = "test",
    kind: LLMProviderKind = LLMProviderKind.OPENAI_COMPATIBLE,
    base_url: str = "https://api.openai.com/v1",
    api_key_enc: str = "",
    is_default: bool = False,
) -> LLMProvider:
    """构造测试用 LLMProvider。"""
    return LLMProvider(
        user_id=uuid.uuid4(),
        name=name,
        kind=kind,
        base_url=base_url,
        api_key_enc=api_key_enc,
        is_default=is_default,
    )

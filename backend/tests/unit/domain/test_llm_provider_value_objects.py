"""domain/llm 值对象单元测试 (v6.20 L1)。

零 mock, 直接构造, 验证值对象行为与协议族属性 + 模板真相源完整性。
"""

from __future__ import annotations

import pytest

from arc.domain.llm.value_objects import (
    PROVIDER_TEMPLATES,
    LLMProviderKind,
    template_by_key,
)


class TestLLMProviderKind:
    def test_openai_compatible_supports_list_models(self) -> None:
        assert LLMProviderKind.OPENAI_COMPATIBLE.supports_list_models is True

    def test_anthropic_not_supports_list_models(self) -> None:
        assert LLMProviderKind.ANTHROPIC.supports_list_models is False

    def test_str_enum_values(self) -> None:
        assert LLMProviderKind.OPENAI_COMPATIBLE.value == "openai_compatible"
        assert LLMProviderKind.ANTHROPIC.value == "anthropic"


class TestProviderTemplates:
    def test_templates_non_empty(self) -> None:
        assert len(PROVIDER_TEMPLATES) >= 7

    def test_template_keys_unique(self) -> None:
        keys = [t.key for t in PROVIDER_TEMPLATES]
        assert len(keys) == len(set(keys))

    def test_openai_template_fields(self) -> None:
        t = template_by_key("openai")
        assert t is not None
        assert t.label == "OpenAI"
        assert t.kind is LLMProviderKind.OPENAI_COMPATIBLE
        assert t.default_base_url == "https://api.openai.com/v1"
        assert "gpt-4o" in t.suggested_models

    def test_anthropic_template_kind(self) -> None:
        t = template_by_key("anthropic")
        assert t is not None
        assert t.kind is LLMProviderKind.ANTHROPIC
        assert t.default_base_url == ""  # 用 SDK 默认端点

    def test_orcarouter_template_fields(self) -> None:
        t = template_by_key("orcarouter")
        assert t is not None
        assert t.kind is LLMProviderKind.OPENAI_COMPATIBLE
        assert t.default_base_url == "https://api.orcarouter.ai/v1"
        assert "gpt-4o" in t.suggested_models

    def test_template_by_key_miss(self) -> None:
        assert template_by_key("nonexistent") is None

    def test_custom_template_exists(self) -> None:
        assert template_by_key("custom") is not None

    def test_all_templates_have_valid_kind(self) -> None:
        for t in PROVIDER_TEMPLATES:
            assert isinstance(t.kind, LLMProviderKind)

    def test_provider_template_frozen(self) -> None:
        t = template_by_key("openai")
        assert t is not None
        with pytest.raises(AttributeError):
            t.label = "changed"  # type: ignore[misc]

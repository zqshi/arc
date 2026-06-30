"""LLMProvider 仓储 _to_entity 映射单元测试 (v6.20 L2)。

纯映射测试, 不依赖 DB session (验证 ORM model → domain entity 字段对齐 + None 兜底)。
CRUD 全路径在 L6 集成测覆盖 (真 DB session)。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from arc.domain.llm.value_objects import LLMProviderKind
from arc.infrastructure.models.llm_provider import LLMProviderModel
from arc.infrastructure.repositories.llm_provider import (
    SqlAlchemyLLMProviderRepository,
)


def _make_model(
    *,
    kind: str = "openai_compatible",
    api_key_enc: str = "enc(token)",
    models: list | None = None,
    is_default: bool = True,
    name: str = "我的OpenAI",
) -> LLMProviderModel:
    """构造 ORM model (绕过 DB server_default, 手动设 timestamp)。"""
    model = LLMProviderModel(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name=name,
        kind=kind,
        base_url="https://api.openai.com/v1",
        api_key_enc=api_key_enc,
        models=models if models is not None else ["gpt-4o", "gpt-4o-mini"],
        is_default=is_default,
    )
    ts = datetime(2026, 6, 30, tzinfo=UTC)
    model.created_at = ts
    model.updated_at = ts
    return model


class TestLLMProviderRepositoryMapping:
    def test_to_entity_full_fields(self) -> None:
        model = _make_model()
        entity = SqlAlchemyLLMProviderRepository._to_entity(model)

        assert entity.id == model.id
        assert entity.user_id == model.user_id
        assert entity.name == "我的OpenAI"
        assert entity.kind is LLMProviderKind.OPENAI_COMPATIBLE
        assert entity.base_url == "https://api.openai.com/v1"
        assert entity.api_key_enc == "enc(token)"
        assert entity.models == ["gpt-4o", "gpt-4o-mini"]
        assert entity.is_default is True
        assert entity.created_at == model.created_at

    def test_to_entity_kind_anthropic(self) -> None:
        model = _make_model(kind="anthropic", api_key_enc="", models=[], is_default=False)
        entity = SqlAlchemyLLMProviderRepository._to_entity(model)

        assert entity.kind is LLMProviderKind.ANTHROPIC
        assert entity.has_api_key() is False
        assert entity.models == []

    def test_to_entity_models_none_defaults_empty(self) -> None:
        """models JSONB 为 None (历史/异常数据) 时兜底为空列表。"""
        model = LLMProviderModel(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            name="x",
            kind="openai_compatible",
            base_url="",
            api_key_enc="",
            models=None,  # type: ignore[arg-type]
            is_default=False,
        )
        model.created_at = datetime.now(UTC)
        model.updated_at = model.created_at
        entity = SqlAlchemyLLMProviderRepository._to_entity(model)
        assert entity.models == []

    def test_to_entity_copies_models(self) -> None:
        """映射复制 models 列表, 避免外部突变。"""
        model = _make_model(models=["a", "b"])
        entity = SqlAlchemyLLMProviderRepository._to_entity(model)
        entity.models.append("c")
        assert model.models == ["a", "b"]  # ORM model 不受 entity 修改影响

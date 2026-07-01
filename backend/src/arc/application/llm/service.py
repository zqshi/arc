"""LLM provider application service (v6.20 L4) — CRUD + 在线探活编排。

编排 LLMProvider 聚合 + LLMProviderRepository + adapter 探活 (list_models/verify)。
加解密通过 infrastructure.crypto 延迟 import (同 deployment/service.py:330 模式,
domain 不依赖 infrastructure, DDD 合规)。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.llm.entity import LLMProvider
from arc.domain.llm.repository import LLMProviderRepository
from arc.domain.llm.value_objects import LLMProviderKind


@dataclass(frozen=True)
class VerifyResult:
    """凭证探活结果 (verify_credentials 返回, 供 interface 转 schema)。"""

    valid: bool
    models: list[str] = field(default_factory=list)
    error_kind: str = ""  # invalid_key | http_error | network | unknown | ""
    error_message: str = ""


def _encrypt(plaintext: str) -> str:
    """加密 (延迟 import infrastructure.crypto, 同 deployment service 模式)。"""
    from arc.infrastructure.crypto import encrypt

    return encrypt(plaintext)


def _decrypt(token: str) -> str:
    """解密 (延迟 import infrastructure.crypto)。"""
    from arc.infrastructure.crypto import decrypt

    return decrypt(token)


class LLMProviderService:
    """LLM 厂商凭证管理 + 探活编排 (用户级隔离, user_id 由调用方传)。"""

    def __init__(self, db: AsyncSession) -> None:
        from arc.infrastructure.repositories.llm_provider import (
            SqlAlchemyLLMProviderRepository,
        )

        self._db = db
        self._repo: LLMProviderRepository = SqlAlchemyLLMProviderRepository(db)

    # -- CRUD ---------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        kind: LLMProviderKind,
        base_url: str,
        api_key: str,
        is_default: bool = False,
    ) -> LLMProvider:
        provider = LLMProvider(
            user_id=user_id, name=name, kind=kind, base_url=base_url
        )
        provider.set_api_key(api_key, _encrypt)
        # is_default 不在 create 时直接写 (会撞部分唯一索引),
        # 先 insert is_default=False, 再 set_default 互斥切换
        created = await self._repo.create(provider)
        if is_default:
            await self._repo.set_default(created.id, user_id)
            created.mark_default()
        return created

    async def list(
        self, user_id: uuid.UUID, *, skip: int = 0, limit: int = 50
    ) -> list[LLMProvider]:
        return await self._repo.list_by_user(user_id, skip=skip, limit=limit)

    async def get(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> LLMProvider | None:
        return await self._repo.get_by_id(provider_id, user_id)

    async def update(
        self,
        provider_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        is_default: bool | None = None,
    ) -> LLMProvider:
        provider = await self._repo.get_by_id(provider_id, user_id)
        if not provider:
            raise ValueError(f"LLMProvider not found: {provider_id}")
        if name is not None:
            provider.rename(name)
        if base_url is not None:
            provider.update_endpoint(base_url)
        if api_key is not None:
            provider.set_api_key(api_key, _encrypt)
        if is_default is True:
            provider.mark_default()
        elif is_default is False:
            provider.clear_default()
        await self._repo.update(provider)
        if is_default is True:
            await self._repo.set_default(provider_id, user_id)
        return provider

    async def delete(self, provider_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return await self._repo.delete(provider_id, user_id)

    async def set_default(
        self, provider_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        await self._repo.set_default(provider_id, user_id)

    # -- 探活 ---------------------------------------------------------------

    async def verify_credentials(
        self,
        *,
        kind: LLMProviderKind,
        base_url: str,
        api_key: str,
    ) -> VerifyResult:
        """验临时凭证 (前端传未保存的 key+base_url), 成功顺带返模型清单。"""
        if not api_key:
            return VerifyResult(
                valid=False, error_kind="invalid_key", error_message="api_key 为空"
            )
        adapter = self._build_adapter(kind, base_url, api_key)
        try:
            if kind.supports_list_models:
                models = await adapter.list_models()
            else:
                await adapter.verify()
                models = await adapter.list_models()
            return VerifyResult(valid=True, models=models)
        except Exception as exc:
            return self._classify_error(exc)
        finally:
            await adapter.close()

    async def list_models(
        self,
        provider_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        refresh: bool = False,
    ) -> list[str]:
        """读已存凭证模型清单 (DB 缓存 provider.models), 空或 refresh 则拉取回填。

        无 api_key 或拉取失败 → 返已有缓存 (不抛, graceful)。
        """
        provider = await self._repo.get_by_id(provider_id, user_id)
        if not provider:
            raise ValueError(f"LLMProvider not found: {provider_id}")
        if provider.models and not refresh:
            return provider.models
        api_key = provider.get_api_key(_decrypt)
        if not api_key:
            return provider.models
        adapter = self._build_adapter(provider.kind, provider.base_url, api_key)
        try:
            models = await adapter.list_models()
        except Exception:
            return provider.models  # 拉取失败返缓存 (如 401)
        finally:
            await adapter.close()
        provider.set_models(models)
        await self._repo.update(provider)
        return models

    # -- LLM 配置解析 (v6.21 D1/D3) ----------------------------------------

    async def resolve_from_project(
        self, project, user_id: uuid.UUID
    ) -> dict | None:
        """解析项目 LLM 配置为 adapter 可用的 dict (D1+D3 统一入口)。

        优先级链:
        1. 项目级 llm_provider_id → DB 凭证 (Fernet 解密)
        2. 旧明文 conversation_config["llm"] (迁移期兼容)
        3. 用户默认凭证 (is_default=True) → DB 解密  ← D1 新增
        4. None (调用方走 adapter_pool _DEFAULT_KEY = env 兜底)

        返回 {provider, model, api_key, base_url} 或 None。统一 conversation_context
        (unified 路径) 与 conversation/service (pipeline 路径) 的 LLM 配置解析, 消除重复。
        """
        # 1. 项目级 LLM 凭证指针 → DB 凭证
        if project.llm_provider_id:
            provider = await self._repo.get_by_id(project.llm_provider_id, user_id)
            if provider and provider.has_api_key():
                return self._provider_to_config(provider)

        # 2. 旧明文 conversation_config["llm"] (向后兼容, 迁移期共存)
        if project.conversation_config:
            legacy = project.conversation_config.get("llm")
            if legacy and legacy.get("api_key"):
                return legacy

        # 3. 用户默认凭证 (D1: 全局默认走 DB, 非 env)
        return await self.resolve_default_config(user_id)

    async def resolve_default_config(
        self, user_id: uuid.UUID
    ) -> dict | None:
        """解析用户默认 LLM 配置 (D1): is_default=True 凭证 → DB 解密 → dict。

        供无项目级覆盖的 Agent 主链路调用方 (extract_tags / text-only 等) 使用,
        让"设置页设默认凭证"生效到非项目级路径。无默认或未配 api_key → None
        (调用方走 adapter_pool _DEFAULT_KEY = env 兜底, 保持 v6.20 渐进边界)。
        """
        provider = await self._repo.get_default(user_id)
        if provider and provider.has_api_key():
            return self._provider_to_config(provider)
        return None

    @staticmethod
    def _provider_to_config(provider: LLMProvider) -> dict:
        """LLMProvider → adapter 可用 dict (解密 api_key, 复用 create_llm_adapter_from_config)。"""
        return {
            "provider": provider.kind.value,
            "model": provider.models[0] if provider.models else "",
            "api_key": provider.get_api_key(_decrypt),
            "base_url": provider.base_url,
        }

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _build_adapter(kind: LLMProviderKind, base_url: str, api_key: str):
        """构造临时 adapter (verify/list_models 用, 调用方负责 close)。"""
        if kind is LLMProviderKind.OPENAI_COMPATIBLE:
            from arc.application.ai.openai_adapter import OpenAIAdapter

            return OpenAIAdapter(
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
            )
        from arc.application.ai.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(api_key=api_key, base_url=base_url)

    @staticmethod
    def _classify_error(exc: Exception) -> VerifyResult:
        """按 SDK 异常 status_code/类型分类探活错误。"""
        status = getattr(exc, "status_code", None)
        if status in (401, 403):
            return VerifyResult(
                valid=False, error_kind="invalid_key", error_message=str(exc)
            )
        if status is not None:
            return VerifyResult(
                valid=False, error_kind="http_error", error_message=str(exc)
            )
        name = type(exc).__name__.lower()
        msg = str(exc).lower()
        if "connect" in name or "timeout" in name or "connect" in msg or "timed out" in msg:
            return VerifyResult(
                valid=False, error_kind="network", error_message=str(exc)
            )
        return VerifyResult(
            valid=False, error_kind="unknown", error_message=str(exc)
        )

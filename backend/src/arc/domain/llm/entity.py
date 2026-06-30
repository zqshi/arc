"""LLM provider 聚合根 — 用户级多厂商凭证 (v6.20 L1)。

一个 LLMProvider 实例 = 用户配置的一个 LLM 厂商 (如 "我的OpenAI" / "国内代理" / "本地ollama"),
含 base_url + api_key (加密) + 模型清单 (verify 时拉取缓存)。

api_key 加解密通过注入式 (set_api_key(encrypt_fn) / get_api_key(decrypt_fn)),
与签名凭证 (Project.set_signing_creds, entity.py:163) 同构 — 加解密函数由 application 层
注入 infrastructure/crypto, 避免 domain→infrastructure 违规。

选用关系:
- 全局默认: 该用户 is_default=True 的唯一凭证 (部分唯一索引在 ORM 层保证)
- 项目级覆盖: Project.llm_provider_id 指向某条凭证 (替代旧 conversation_config["llm"] 明文)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.llm.value_objects import LLMProviderKind


@dataclass
class LLMProvider:
    """用户级 LLM 厂商凭证聚合根。"""

    user_id: uuid.UUID
    name: str
    kind: LLMProviderKind
    base_url: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    api_key_enc: str = field(default="", repr=False)  # Fernet token (空=未配, repr 隐藏)
    models: list[str] = field(default_factory=list)  # 模型清单缓存 (verify 拉取回填)
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # -- API key 加解密 (注入式, 同签名凭证) -------------------------------

    def set_api_key(self, api_key: str, encrypt_fn) -> None:
        """加密存储 api_key。空串 → 清空 (保持未配状态)。"""
        self.api_key_enc = encrypt_fn(api_key) if api_key else ""
        self.updated_at = datetime.now(UTC)

    def get_api_key(self, decrypt_fn) -> str:
        """解密读取 api_key, 未配 (token 空) 返回空串。"""
        if not self.api_key_enc:
            return ""
        return decrypt_fn(self.api_key_enc)

    def has_api_key(self) -> bool:
        """是否已配置 api_key (不解密, 用于 GET 响应 api_key_set, 避免明文)。"""
        return bool(self.api_key_enc)

    # -- 模型清单 ---------------------------------------------------------

    def set_models(self, models: list[str]) -> None:
        """更新缓存的模型清单 (verify/list_models 拉取后回填, 复制避免外部突变)。"""
        self.models = list(models)
        self.updated_at = datetime.now(UTC)

    # -- 默认标记 ---------------------------------------------------------

    def mark_default(self) -> None:
        """标记为该用户全局默认。

        互斥切换 (取消同用户其他 default) 由 repository.set_default 处理。
        """
        self.is_default = True
        self.updated_at = datetime.now(UTC)

    def clear_default(self) -> None:
        """取消全局默认标记。"""
        self.is_default = False
        self.updated_at = datetime.now(UTC)

    # -- 字段更新 ---------------------------------------------------------

    def rename(self, name: str) -> None:
        """重命名厂商配置。"""
        if not name:
            raise ValueError("name is required")
        self.name = name
        self.updated_at = datetime.now(UTC)

    def update_endpoint(self, base_url: str) -> None:
        """更新 base_url (端点变更后模型清单应重新拉取, 调用方负责清缓存)。"""
        self.base_url = base_url
        self.updated_at = datetime.now(UTC)

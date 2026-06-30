"""LLMProvider ORM 模型 (v6.20 L2) — 用户级多厂商 LLM 凭证。

api_key_enc 存 Fernet 加密 token (加密在 application service 层注入 crypto.encrypt 完成,
同签名凭证 Project.enc_*_creds 模式, repo 只存取密文 token, 不碰 crypto)。models 缓存
verify 时拉取的模型清单。部分唯一索引保证每用户至多一个 is_default=true (全局默认)。
"""
import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class LLMProviderModel(TimestampMixin, Base):
    __tablename__ = "llm_providers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # openai_compatible | anthropic
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    api_key_enc: Mapped[str] = mapped_column(Text, nullable=False, default="")
    models: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # 部分唯一索引: 每用户至多一个 is_default=true (全局默认互斥)
        Index(
            "uq_llm_providers_user_default",
            "user_id",
            unique=True,
            postgresql_where=sa.text("is_default = true"),
        ),
    )

"""Capability ORM 模型 (v6.8.0 W1)。

能力声明表 — agent/skill 的可管理能力 (注册表项)。config 为 JSONB 配置载荷,
按 type 由 loader 解释 (W2)。与 deployment/signer 的静态注册不同, capability 走 DB 声明管理。
"""
import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CapabilityModel(TimestampMixin, Base):
    __tablename__ = "capabilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", index=True
    )
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="global", index=True
    )

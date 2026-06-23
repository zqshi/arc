"""DomainTemplate ORM 模型 (v5.7.0)。"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class DomainTemplateModel(TimestampMixin, Base):
    __tablename__ = "domain_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # 元信息
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(30), default="custom", nullable=False)

    # 来源追溯
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    source_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    source_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # 核心内容
    schema_template: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    entity_patterns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    state_machine_patterns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    permission_patterns: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # 搜索
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)

    # 生命周期
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="personal", nullable=False)

    # 统计
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 衰减
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

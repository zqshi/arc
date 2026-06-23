"""BaasInstance ORM 模型 (v5.6.0)。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class BaasInstanceModel(TimestampMixin, Base):
    __tablename__ = "baas_instances"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    supabase_url: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="provisioning", nullable=False)
    last_applied_model_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

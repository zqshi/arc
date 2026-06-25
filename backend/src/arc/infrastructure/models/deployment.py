"""Deployment ORM 模型。"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class DeploymentModel(TimestampMixin, Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    todo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("todos.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    deploy_type: Mapped[str] = mapped_column(String(30), default="static_site", nullable=False)

    build_command: Mapped[str] = mapped_column(String(200), default="npm run build")
    artifact_path: Mapped[str] = mapped_column(String(200), default="dist")

    deploy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_prefix: Mapped[str | None] = mapped_column(String(500), nullable=True)
    files_uploaded: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    distribution_manifest: Mapped[str | None] = mapped_column(Text, nullable=True)  # v6.2.0 T5

    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ProjectModel(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_stack: Mapped[str | None] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conventions: Mapped[str | None] = mapped_column(Text, nullable=True)
    codebase_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_fingerprint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="idle", server_default="idle")
    scan_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    execution_mode: Mapped[str] = mapped_column(String(20), default="pipeline")
    pipeline_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    conversation_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    domain_model: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    github_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    github_webhook_secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    github_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class VersionModel(TimestampMixin, Base):
    __tablename__ = "versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planning")
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    changelog: Mapped[str | None] = mapped_column(Text, nullable=True)

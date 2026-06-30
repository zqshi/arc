import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Experience(TimestampMixin, Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    todo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_experience_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiences.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="project", index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    category: Mapped[str] = mapped_column(String(30), default="technical")
    source: Mapped[str] = mapped_column(String(30), default="manual")
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    decisions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pitfalls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    applicable_scenarios: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(1536), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reuse_count: Mapped[int] = mapped_column(Integer, default=0)
    half_life_days: Mapped[int] = mapped_column(Integer, default=180, server_default="180")
    last_reused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class ExperienceFeedback(TimestampMixin, Base):
    __tablename__ = "experience_feedback"
    __table_args__ = (
        UniqueConstraint("experience_id", "todo_id", name="uq_exp_feedback_exp_todo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"), nullable=False
    )
    todo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)

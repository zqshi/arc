import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Experience(TimestampMixin, Base):
    __tablename__ = "experiences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    todo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), default="project")
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
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=False
    )
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)

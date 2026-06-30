import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class TodoDependency(Base):
    __tablename__ = "todo_dependencies"
    __table_args__ = (
        UniqueConstraint("todo_id", "depends_on_id", name="uq_todo_dependency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    todo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Todo(TimestampMixin, Base):
    __tablename__ = "todos"
    __table_args__ = (
        Index("ix_todos_created_at", "created_at"),
        Index("ix_todos_github_issue", "project_id", "github_issue_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=2)
    current_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planning_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_feature_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    github_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    github_pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspended_model_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

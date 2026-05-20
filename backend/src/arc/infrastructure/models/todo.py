import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Todo(TimestampMixin, Base):
    __tablename__ = "todos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("versions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    priority: Mapped[int] = mapped_column(Integer, default=2)
    current_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(20), default="pipeline")
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planning_sessions.id", ondelete="SET NULL"), nullable=True
    )
    source_feature_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

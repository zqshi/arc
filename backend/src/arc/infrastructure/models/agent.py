import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AgentSessionModel(TimestampMixin, Base):
    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    todo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("todos.id", ondelete="CASCADE"), nullable=False)
    phase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pipeline_phases.id", ondelete="CASCADE"), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    external_session_id: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    task_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_reason: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

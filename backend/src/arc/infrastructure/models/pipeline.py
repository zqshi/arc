import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class PipelinePhaseModel(TimestampMixin, Base):
    __tablename__ = "pipeline_phases"
    __table_args__ = (
        UniqueConstraint("todo_id", "phase_type", name="uq_pipeline_phases_todo_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    todo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phase_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, index=True
    )
    agent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_sessions.id"), nullable=True, index=True
    )

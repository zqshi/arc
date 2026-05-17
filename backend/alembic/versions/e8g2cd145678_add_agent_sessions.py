"""add agent_sessions table and pipeline_phases.agent_session_id

Revision ID: e8g2cd145678
Revises: d7f1bc034567
Create Date: 2026-05-17 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e8g2cd145678"
down_revision = "d7f1bc034567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("todo_id", sa.Uuid(), nullable=False),
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.Column("agent_type", sa.String(30), nullable=False),
        sa.Column("external_session_id", sa.String(255), server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("task_context", postgresql.JSONB(), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(), nullable=True),
        sa.Column("error_reason", sa.Text(), server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phase_id"], ["pipeline_phases.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_agent_sessions_todo_id", "agent_sessions", ["todo_id"])
    op.create_index("ix_agent_sessions_phase_id", "agent_sessions", ["phase_id"])
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"])

    op.add_column(
        "pipeline_phases",
        sa.Column("agent_session_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pipeline_phases_agent_session",
        "pipeline_phases",
        "agent_sessions",
        ["agent_session_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_pipeline_phases_agent_session", "pipeline_phases", type_="foreignkey")
    op.drop_column("pipeline_phases", "agent_session_id")
    op.drop_index("ix_agent_sessions_status", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_phase_id", table_name="agent_sessions")
    op.drop_index("ix_agent_sessions_todo_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")

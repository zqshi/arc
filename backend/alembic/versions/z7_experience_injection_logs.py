"""add experience_injection_logs table

Revision ID: z7_experience_injection_logs
Revises: z6_deployments
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "z7_experience_injection_logs"
down_revision = "z6_deployments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experience_injection_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "experience_id",
            UUID(as_uuid=True),
            sa.ForeignKey("experiences.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "todo_id",
            UUID(as_uuid=True),
            sa.ForeignKey("todos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("similarity_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("todo_completed", sa.Boolean, nullable=True),
        sa.Column("rounds_after_injection", sa.Integer, nullable=True),
        sa.Column("user_feedback", sa.Boolean, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("experience_injection_logs")

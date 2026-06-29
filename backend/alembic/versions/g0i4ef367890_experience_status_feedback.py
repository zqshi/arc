"""add experience status column and feedback table

Revision ID: g0i4ef367890
Revises: f9h3de256789
Create Date: 2026-05-17
"""

import sqlalchemy as sa

from alembic import op

revision = "g0i4ef367890"
down_revision = "f9h3de256789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiences",
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
    )
    op.execute("UPDATE experiences SET scope = 'project' WHERE scope = 'todo'")
    op.execute("UPDATE experiences SET status = 'confirmed' WHERE status = 'draft'")

    op.create_table(
        "experience_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "experience_id",
            sa.Uuid(),
            sa.ForeignKey("experiences.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "todo_id",
            sa.Uuid(),
            sa.ForeignKey("todos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "experience_id", "todo_id", name="uq_exp_feedback_exp_todo"
        ),
    )


def downgrade() -> None:
    op.drop_table("experience_feedback")
    op.drop_column("experiences", "status")

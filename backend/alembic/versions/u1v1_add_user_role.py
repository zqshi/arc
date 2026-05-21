"""add role column to users

Revision ID: u1v1_add_user_role
Revises: t1t3_experience_decay_distill
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa

revision = "u1v1_add_user_role"
down_revision = "t1t3_experience_decay_distill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), server_default="admin", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "role")

"""add last_reused_at to experiences for decay anchor

Revision ID: z4_experience_last_reused
Revises: z3_github_integration
"""
from alembic import op
import sqlalchemy as sa

revision = "z4_experience_last_reused"
down_revision = "z3_github_integration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiences", sa.Column("last_reused_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("experiences", "last_reused_at")

"""add version_analyses table

Revision ID: r1_version_analysis
Revises: (auto)
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa


revision = "r1_version_analysis"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "version_analyses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["version_id"], ["versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_version_analyses_version_id", "version_analyses", ["version_id"])
    op.create_index("ix_version_analyses_fingerprint", "version_analyses", ["version_id", "fingerprint"])


def downgrade() -> None:
    op.drop_table("version_analyses")

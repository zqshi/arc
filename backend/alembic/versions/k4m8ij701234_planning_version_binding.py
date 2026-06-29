"""add version_id to planning_sessions, allow revision from applied

Revision ID: k4m8ij701234
Revises: j3l7hi690123
Create Date: 2026-05-20
"""

import sqlalchemy as sa

from alembic import op

revision = "k4m8ij701234"
down_revision = "j3l7hi690123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planning_sessions",
        sa.Column("version_id", sa.UUID(), sa.ForeignKey("versions.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_planning_sessions_version_id", "planning_sessions", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_planning_sessions_version_id", "planning_sessions")
    op.drop_column("planning_sessions", "version_id")

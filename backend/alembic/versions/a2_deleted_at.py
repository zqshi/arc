"""add deleted_at to projects

Revision ID: a2_deleted_at
Revises: a1_scan_status
Create Date: 2026-05-30
"""

import sqlalchemy as sa

from alembic import op

revision = "a2_deleted_at"
down_revision = "a1_scan_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "deleted_at")

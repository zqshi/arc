"""add scan_status scan_progress scan_error to projects

Revision ID: a1_scan_status
Revises: k4m8ij701234
Create Date: 2026-05-30
"""

import sqlalchemy as sa

from alembic import op

revision = "a1_scan_status"
down_revision = "7d587912c43d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("scan_status", sa.String(20), server_default="idle", nullable=False))
    op.add_column("projects", sa.Column("scan_progress", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("scan_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "scan_error")
    op.drop_column("projects", "scan_progress")
    op.drop_column("projects", "scan_status")

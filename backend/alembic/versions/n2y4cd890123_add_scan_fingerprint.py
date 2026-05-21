"""add scan_fingerprint to projects

Revision ID: n2y4cd890123
Revises: m1x3ab567890
Create Date: 2026-05-20 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "n2y4cd890123"
down_revision = "m1x3ab567890"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("scan_fingerprint", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "scan_fingerprint")

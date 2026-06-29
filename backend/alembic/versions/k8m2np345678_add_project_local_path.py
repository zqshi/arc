"""add project local_path

Revision ID: k8m2np345678
Revises: l5n9jk812345
Create Date: 2026-05-20 16:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "k8m2np345678"
down_revision = "l5n9jk812345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("local_path", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "local_path")

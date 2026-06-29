"""add project codebase_summary

Revision ID: m1x3ab567890
Revises: k8m2np345678
Create Date: 2026-05-20 18:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "m1x3ab567890"
down_revision = "k8m2np345678"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("codebase_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "codebase_summary")

"""add preview_url to artifacts

Revision ID: x1_preview_url
Revises: w1_domain_model
"""

import sqlalchemy as sa

from alembic import op

revision = "x1_preview_url"
down_revision = "w1_domain_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifacts", sa.Column("preview_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("artifacts", "preview_url")

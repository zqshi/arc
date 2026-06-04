"""add prototype_preview_url to versions

Revision ID: z5_version_preview_url
Revises: z4_experience_last_reused
"""
from alembic import op
import sqlalchemy as sa

revision = "z5_version_preview_url"
down_revision = "z4_experience_last_reused"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("versions", sa.Column("prototype_preview_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("versions", "prototype_preview_url")

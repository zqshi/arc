"""add last_seen_at to todos

Revision ID: q4a6fg123456
Revises: p3z5ef012345
"""

import sqlalchemy as sa

from alembic import op

revision = "q4a6fg123456"
down_revision = "p3z5ef012345"


def upgrade() -> None:
    op.add_column("todos", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("todos", "last_seen_at")

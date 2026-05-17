"""add scope column to experiences

Revision ID: d7f1bc034567
Revises: c6e0ab923456
Create Date: 2026-05-17 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d7f1bc034567"
down_revision = "c6e0ab923456"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiences",
        sa.Column("scope", sa.String(20), server_default="todo", nullable=False),
    )
    op.create_index("ix_experiences_scope", "experiences", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_experiences_scope", table_name="experiences")
    op.drop_column("experiences", "scope")

"""add usage_daily table for quota tracking

Revision ID: z2_usage_daily
Revises: z1_multi_tenant
"""

import sqlalchemy as sa

from alembic import op

revision = "z2_usage_daily"
down_revision = "z1_multi_tenant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("ai_calls", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_daily_org_date", "usage_daily", ["organization_id", "usage_date"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_usage_daily_org_date", table_name="usage_daily")
    op.drop_table("usage_daily")

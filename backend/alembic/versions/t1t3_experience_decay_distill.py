"""add experience decay and distill fields

Revision ID: t1t3_decay_distill
Revises: s6a9bc456789
Create Date: 2026-05-21

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "t1t3_decay_distill"
down_revision = "s6a9bc456789"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiences", sa.Column("half_life_days", sa.Integer(), server_default="180", nullable=False))
    op.add_column("experiences", sa.Column("source_experience_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_experience_source",
        "experiences",
        "experiences",
        ["source_experience_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_experiences_source_experience_id", "experiences", ["source_experience_id"])


def downgrade() -> None:
    op.drop_index("ix_experiences_source_experience_id", table_name="experiences")
    op.drop_constraint("fk_experience_source", "experiences", type_="foreignkey")
    op.drop_column("experiences", "source_experience_id")
    op.drop_column("experiences", "half_life_days")

"""add domain_model column to projects

Revision ID: w1_domain_model
Revises: u2v4_missing_fk_idx, u1v1_add_user_role
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "w1_domain_model"
down_revision = ("u2v4_missing_fk_idx", "u1v1_add_user_role")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("domain_model", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "domain_model")

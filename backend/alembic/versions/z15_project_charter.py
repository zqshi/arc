"""add project charter column (v6.3.0 T1)

Revision ID: z15_project_charter
Revises: z14_distribution_manifest
Create Date: 2026-06-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "z15_project_charter"
down_revision: Union[str, None] = "z14_distribution_manifest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("charter", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "charter")

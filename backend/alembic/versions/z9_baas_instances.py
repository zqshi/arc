"""add baas_instances table

Revision ID: z9_baas_instances
Revises: z8_context_policy
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z9_baas_instances"
down_revision: Union[str, None] = "z8_context_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "baas_instances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("schema_name", sa.String(100), nullable=False),
        sa.Column("supabase_url", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="provisioning"),
        sa.Column("last_applied_model_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", name="uq_baas_instances_project_id"),
        sa.UniqueConstraint("schema_name", name="uq_baas_instances_schema_name"),
    )
    op.create_index("ix_baas_instances_project_id", "baas_instances", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_baas_instances_project_id", table_name="baas_instances")
    op.drop_table("baas_instances")

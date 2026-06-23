"""add domain_templates table

Revision ID: z10_domain_templates
Revises: z9_baas_instances
Create Date: 2026-06-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "z10_domain_templates"
down_revision: Union[str, None] = "z9_baas_instances"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_templates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category", sa.String(30), nullable=False, server_default="custom"),
        sa.Column("source_project_id", sa.UUID(), nullable=True),
        sa.Column("source_version_id", sa.UUID(), nullable=True),
        sa.Column("source_user_id", sa.UUID(), nullable=False),
        sa.Column("schema_template", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("entity_patterns", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("state_machine_patterns", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("permission_patterns", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("tags", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="personal"),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.8"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_version_id"], ["versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_user_id"], ["users.id"]),
    )
    op.create_index("ix_domain_templates_source_user_id", "domain_templates", ["source_user_id"])
    op.create_index("ix_domain_templates_status", "domain_templates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_domain_templates_status", table_name="domain_templates")
    op.drop_index("ix_domain_templates_source_user_id", table_name="domain_templates")
    op.drop_table("domain_templates")

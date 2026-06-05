"""add deployments table and version deploy_url

Revision ID: z6_deployments
Revises: z5_version_preview_url
"""
from alembic import op
import sqlalchemy as sa

revision = "z6_deployments"
down_revision = "cc9223296e15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deployments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("todo_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("deploy_type", sa.String(30), nullable=False, server_default="static_site"),
        sa.Column("build_command", sa.String(200), server_default="npm run build"),
        sa.Column("artifact_path", sa.String(200), server_default="dist"),
        sa.Column("deploy_url", sa.String(500), nullable=True),
        sa.Column("storage_prefix", sa.String(500), nullable=True),
        sa.Column("files_uploaded", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_deployments_project_id", "deployments", ["project_id"])
    op.create_index("ix_deployments_version_id", "deployments", ["version_id"])

    # Add deploy_url to versions table
    op.add_column("versions", sa.Column("deploy_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("versions", "deploy_url")
    op.drop_index("ix_deployments_version_id", table_name="deployments")
    op.drop_index("ix_deployments_project_id", table_name="deployments")
    op.drop_table("deployments")

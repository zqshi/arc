"""add github integration fields

Revision ID: z3_github_integration
Revises: z2_usage_daily
"""

import sqlalchemy as sa
from alembic import op

revision = "z3_github_integration"
down_revision = "z2_usage_daily"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("github_token", sa.String(500), nullable=True))
    op.add_column("projects", sa.Column("github_webhook_secret", sa.String(200), nullable=True))
    op.add_column("projects", sa.Column("github_config", sa.dialects.postgresql.JSONB(), nullable=True))

    op.add_column("todos", sa.Column("github_issue_number", sa.Integer(), nullable=True))
    op.add_column("todos", sa.Column("github_pr_url", sa.String(500), nullable=True))
    op.create_index(
        "ix_todos_github_issue",
        "todos",
        ["project_id", "github_issue_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_todos_github_issue", table_name="todos")
    op.drop_column("todos", "github_pr_url")
    op.drop_column("todos", "github_issue_number")
    op.drop_column("projects", "github_config")
    op.drop_column("projects", "github_webhook_secret")
    op.drop_column("projects", "github_token")

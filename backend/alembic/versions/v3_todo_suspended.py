"""add todo suspended and error_reason columns

Revision ID: v3_todo_suspended
Revises: v3_domain_model_review
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa

revision = "v3_todo_suspended"
down_revision = "v3_domain_model_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("todos", sa.Column("error_reason", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("suspended_reason", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("suspended_model_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("todos", "suspended_model_version")
    op.drop_column("todos", "suspended_reason")
    op.drop_column("todos", "error_reason")

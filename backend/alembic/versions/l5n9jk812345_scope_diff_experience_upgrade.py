"""scope diff tracking + experience category/source upgrade

Revision ID: l5n9jk812345
Revises: k4m8ij701234
Create Date: 2026-05-20
"""

import sqlalchemy as sa

from alembic import op

revision = "l5n9jk812345"
down_revision = "k4m8ij701234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Todo source tracking for scope diff
    op.add_column("todos", sa.Column("source_session_id", sa.UUID(), nullable=True))
    op.add_column("todos", sa.Column("source_feature_key", sa.String(200), nullable=True))
    op.create_foreign_key(
        "fk_todos_source_session", "todos", "planning_sessions",
        ["source_session_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_todos_source_session_id", "todos", ["source_session_id"])

    # Experience category + source + version binding
    op.add_column("experiences", sa.Column("category", sa.String(30), server_default="technical", nullable=False))
    op.add_column("experiences", sa.Column("source", sa.String(30), server_default="manual", nullable=False))
    op.add_column("experiences", sa.Column("version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_experiences_version", "experiences", "versions",
        ["version_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_experiences_version", "experiences", type_="foreignkey")
    op.drop_column("experiences", "version_id")
    op.drop_column("experiences", "source")
    op.drop_column("experiences", "category")

    op.drop_index("ix_todos_source_session_id", "todos")
    op.drop_constraint("fk_todos_source_session", "todos", type_="foreignkey")
    op.drop_column("todos", "source_feature_key")
    op.drop_column("todos", "source_session_id")

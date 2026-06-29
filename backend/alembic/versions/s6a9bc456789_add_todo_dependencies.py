"""add todo_dependencies table

Revision ID: s6a9bc456789
Revises: r5b7hi234567
Create Date: 2026-05-21

"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "s6a9bc456789"
down_revision = "r5b7hi234567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todo_dependencies",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("todo_id", UUID(as_uuid=True), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("depends_on_id", UUID(as_uuid=True), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("todo_id", "depends_on_id", name="uq_todo_dependency"),
        sa.CheckConstraint("todo_id != depends_on_id", name="ck_no_self_dependency"),
    )
    op.create_index("ix_todo_deps_todo_id", "todo_dependencies", ["todo_id"])
    op.create_index("ix_todo_deps_depends_on_id", "todo_dependencies", ["depends_on_id"])


def downgrade() -> None:
    op.drop_index("ix_todo_deps_depends_on_id")
    op.drop_index("ix_todo_deps_todo_id")
    op.drop_table("todo_dependencies")

"""add domain model history and review feedbacks

Revision ID: v3_domain_model_review
Revises: 7d587912c43d
Create Date: 2026-06-01
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "v3_domain_model_review"
down_revision = "a2_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. projects 表新增 domain_model_history 字段
    op.add_column(
        "projects",
        sa.Column("domain_model_history", JSONB, nullable=True, server_default="[]"),
    )

    # 2. 新建 review_feedbacks 表
    op.create_table(
        "review_feedbacks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_todo_id",
            sa.Uuid(),
            sa.ForeignKey("todos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_version", sa.Integer(), default=0),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("issue", JSONB, nullable=False),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 3. 索引
    op.create_index(
        "ix_review_feedbacks_project_status",
        "review_feedbacks",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_review_feedbacks_project_status")
    op.drop_table("review_feedbacks")
    op.drop_column("projects", "domain_model_history")

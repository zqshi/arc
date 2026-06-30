"""A1 投产门禁: users.role server_default admin→member

注册用户默认 MEMBER (首用户特例/提权才 ADMIN), 消除"任意注册即全局 admin"越权。
arc 未投产无存量用户, server_default 变更无数据影响, 仅对齐 ORM 模型 (A1.1)。

Revision ID: z22_role_default_member
Revises: z21_align_schema_drift
Create Date: 2026-06-30
"""
import sqlalchemy as sa

from alembic import op

revision = "z22_role_default_member"
down_revision = "z21_align_schema_drift"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users", "role", server_default="member", existing_type=sa.String(20)
    )


def downgrade() -> None:
    op.alter_column(
        "users", "role", server_default="admin", existing_type=sa.String(20)
    )

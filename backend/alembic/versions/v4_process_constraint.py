"""add process_constraint column to projects

Revision ID: v4_process_constraint
Revises: v3_todo_suspended
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "v4_process_constraint"
down_revision = "v3_todo_suspended"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增 process_constraint 字段
    op.add_column(
        "projects",
        sa.Column("process_constraint", sa.String(20), server_default="free"),
    )
    op.add_column(
        "projects",
        sa.Column("process_config", JSONB, nullable=True),
    )

    # 数据迁移: execution_mode → process_constraint
    op.execute("""
        UPDATE projects
        SET process_constraint = CASE
            WHEN execution_mode = 'pipeline' THEN 'strict'
            ELSE 'free'
        END
    """)

    # process_config 填充默认值
    op.execute("""
        UPDATE projects
        SET process_config = CASE
            WHEN execution_mode = 'pipeline' THEN
                '{"constraint": "strict", "gate_strictness": "strict", "auto_extract": false, "require_explicit_confirm": true, "show_phase_ui": true}'::jsonb
            ELSE
                '{"constraint": "free", "gate_strictness": "moderate", "auto_extract": true, "require_explicit_confirm": false, "show_phase_ui": false}'::jsonb
        END
    """)


def downgrade() -> None:
    op.drop_column("projects", "process_config")
    op.drop_column("projects", "process_constraint")

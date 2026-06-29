"""drop deprecated execution_mode column from todos and projects

Revision ID: z19_drop_execution_mode
Revises: z18_backfill_process_constraint
Create Date: 2026-06-29

v6.16 T1: execution_mode 字段下线。process_constraint 自 v4 起作为单一真相源,
z18 已按 execution_mode (权威信号) 回填 process_constraint, 现 drop execution_mode 列。
entity/ORM/schema/routes 均已改读 process_constraint, execution_mode 无消费方。

downgrade 恢复列结构 (server_default 'pipeline'), 但原数据不可逆 (依赖 process_constraint 派生)。
"""

from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "z19_drop_execution_mode"
down_revision: Union[str, None] = "z18_backfill_process_constraint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("todos", "execution_mode")
    op.drop_column("projects", "execution_mode")


def downgrade() -> None:
    # 恢复列结构, 原数据不可逆 (依赖 process_constraint 派生)
    op.add_column(
        "todos",
        sa.Column("execution_mode", sa.String(20), server_default="pipeline"),
    )
    op.add_column(
        "projects",
        sa.Column("execution_mode", sa.String(20), server_default="pipeline"),
    )

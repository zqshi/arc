"""backfill process_constraint for projects created with create() bug

Revision ID: z18_backfill_process_constraint
Revises: z17_capabilities
Create Date: 2026-06-28

数据回填 (非 schema 变更): 修正 ProjectRepository.create 漏写 process_constraint/
process_config 导致的存量数据错误。

背景:
- v4_process_constraint 加列时已按 execution_mode 回填过一次, 当时数据正确。
- 但 v4 之后, ProjectRepository.create 构造 ORM model 时漏写 process_constraint/
  process_config 两字段, DB 用 ORM default ("free" / NULL) 静默覆盖。
- 此 bug 潜伏至 e3f6598 (v6.15 T5) 才修复。修复前创建的 strict 项目,
  DB 实际是 free (entity↔DB 不一致), 用户以为设了严格管线但实际跑自由模式。

回填规则 (execution_mode 是权威信号, 因其一直被正确持久化):
- execution_mode='pipeline' AND process_constraint='free'  →  'strict'
  (被 bug 污染的严格管线项目; 不碰 conversation 项目, 其 free 本就正确)
- process_config 统一规整为 T4 后的格式 {"constraint": <值>},
  消除旧 5 字段格式 (gate_strictness 等已删) 与 NULL 混存。

downgrade 为 no-op: 数据回填是修正, 回退会重新引入 bug 数据, 无意义。
若需手动撤销可执行反向 UPDATE。
"""

from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "z18_backfill_process_constraint"
down_revision: Union[str, None] = "z17_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 回填 process_constraint: 被 bug 污染的 pipeline 项目 (误存 free) → strict
    #    只改 process_constraint='free' 的 pipeline 项目, 不碰已是 strict 的 (避免覆盖正确数据)。
    #    conversation 项目的 free 是正确的, 不动。
    op.execute(
        sa.text(
            """
            UPDATE projects
            SET process_constraint = 'strict'
            WHERE execution_mode = 'pipeline'
              AND process_constraint = 'free'
            """
        )
    )

    # 2. 规整 process_config 为 T4 后格式 (仅持 constraint), 消除旧 5 字段格式与 NULL。
    #    从 process_constraint 派生, 保证两字段一致。
    op.execute(
        sa.text(
            """
            UPDATE projects
            SET process_config = jsonb_build_object('constraint', process_constraint)
            """
        )
    )


def downgrade() -> None:
    # no-op: 数据回填是修正, 回退会重新引入 bug 数据。
    pass

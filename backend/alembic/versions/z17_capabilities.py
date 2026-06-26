"""create capabilities table (v6.8.0 W1)

Revision ID: z17_capabilities
Revises: z16_drop_injection_logs
Create Date: 2026-06-26

能力声明表 — agent/skill 可管理能力注册表。config 为 JSONB 配置载荷。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "z17_capabilities"
down_revision: Union[str, None] = "z16_drop_injection_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capabilities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_capabilities_name", "capabilities", ["name"])
    op.create_index("ix_capabilities_type", "capabilities", ["type"])
    op.create_index("ix_capabilities_status", "capabilities", ["status"])
    op.create_index("ix_capabilities_scope", "capabilities", ["scope"])


def downgrade() -> None:
    op.drop_table("capabilities")

"""add project_type column to projects

为项目引入"交付/部署形态"维度 (v5.9.0 项目类型框架)。
与 backend_type(后端形态) / app_code.framework(前端框架) 正交。
本版本仅 static_site 实质值; 存量数据 server_default 回填为 static_site。

Revision ID: z11_project_type
Revises: z10_domain_templates
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z11_project_type"
down_revision: Union[str, None] = "z10_domain_templates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "project_type",
            sa.String(length=30),
            nullable=False,
            server_default="static_site",
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "project_type")

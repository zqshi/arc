"""add distribution_manifest column to deployments

Revision ID: z14_distribution_manifest
Revises: z13_distribution_creds
Create Date: 2026-06-25

v6.2.0 T5: 制品分发清单持久化 (DistributionManifest JSON — 产物+渠道结果的结构化真相,
Arc API + 下载页/更新元数据的渲染源)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z14_distribution_manifest"
down_revision: Union[str, None] = "z13_distribution_creds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deployments", sa.Column("distribution_manifest", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("deployments", "distribution_manifest")

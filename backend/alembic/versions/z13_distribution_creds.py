"""add distribution credentials columns to projects

Revision ID: z13_distribution_creds
Revises: z12_signing_creds
Create Date: 2026-06-24

v6.2.0: 项目维度分发凭证加密存储 (按渠道分字段, 与签名凭证独立)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z13_distribution_creds"
down_revision: Union[str, None] = "z12_signing_creds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("enc_appstore_creds", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("enc_playstore_creds", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("enc_tauri_updater_creds", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "enc_tauri_updater_creds")
    op.drop_column("projects", "enc_playstore_creds")
    op.drop_column("projects", "enc_appstore_creds")

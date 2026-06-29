"""add signing credentials columns to projects

Revision ID: z12_signing_creds
Revises: z11_project_type
Create Date: 2026-06-24

v6.1.0: 项目维度签名凭证加密存储 (按平台分字段, Fernet base64 token)。
接在 z11_project_type (v5.9.0 项目类型) 之后。
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "z12_signing_creds"
down_revision: Union[str, None] = "z11_project_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("enc_apple_creds", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("enc_win_creds", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("enc_android_creds", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "enc_android_creds")
    op.drop_column("projects", "enc_win_creds")
    op.drop_column("projects", "enc_apple_creds")

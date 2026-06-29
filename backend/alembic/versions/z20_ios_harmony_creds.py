"""add iOS/Harmony signing credentials columns to projects

Revision ID: z20_ios_harmony_creds
Revises: z19_drop_execution_mode
Create Date: 2026-06-29

v6.19 T7/T10: iOS + 鸿蒙签名凭证加密存储 (按平台分字段, Fernet base64 token)。
与 z12_signing_creds (apple/win/android) 同构: 新增 enc_ios_creds / enc_harmony_creds
两列, 供 SignerType.IOS/HARMONY 配套签名器读取 (infrastructure/signer/{ios,harmony}.py)。
KIND_SIGNER_TYPE[IPA/HAP] 已回填 IOS/HARMONY, 列就位后凭证链路闭环。
"""

from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "z20_ios_harmony_creds"
down_revision: Union[str, None] = "z19_drop_execution_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("enc_ios_creds", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("enc_harmony_creds", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "enc_harmony_creds")
    op.drop_column("projects", "enc_ios_creds")

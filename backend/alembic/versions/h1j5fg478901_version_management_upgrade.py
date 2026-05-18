"""version management upgrade: parent_version_id, order, changelog

Revision ID: h1j5fg478901
Revises: g0i4ef367890
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "h1j5fg478901"
down_revision = "g0i4ef367890"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("versions", sa.Column("parent_version_id", sa.Uuid(), nullable=True))
    op.add_column("versions", sa.Column("order", sa.Integer(), server_default="0", nullable=False))
    op.add_column("versions", sa.Column("changelog", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_versions_parent_version_id",
        "versions",
        "versions",
        ["parent_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("""
        WITH ordered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY created_at ASC) AS rn
            FROM versions
        )
        UPDATE versions SET "order" = ordered.rn
        FROM ordered WHERE versions.id = ordered.id
    """)


def downgrade() -> None:
    op.drop_constraint("fk_versions_parent_version_id", "versions", type_="foreignkey")
    op.drop_column("versions", "changelog")
    op.drop_column("versions", "order")
    op.drop_column("versions", "parent_version_id")

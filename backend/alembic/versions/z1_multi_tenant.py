"""add multi-tenant: organizations, organization_members, projects.organization_id

Revision ID: z1_multi_tenant
Revises: y2_revoked_tokens
"""

import sqlalchemy as sa
from alembic import op

revision = "z1_multi_tenant"
down_revision = "y2_revoked_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("plan", sa.String(20), server_default="free", nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members"),
    )
    op.create_index("ix_org_members_org_id", "organization_members", ["organization_id"])
    op.create_index("ix_org_members_user_id", "organization_members", ["user_id"])

    op.add_column(
        "projects",
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])

    # --- backfill: create a default org for each existing user, assign their projects ---
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, display_name FROM users")).fetchall()
    for user_id, display_name in users:
        import uuid

        org_id = uuid.uuid4()
        slug = f"user-{str(user_id).replace('-', '')[:12]}"
        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug, plan, is_active) "
                "VALUES (:id, :name, :slug, 'free', true)"
            ),
            {"id": org_id, "name": f"{display_name}的工作区", "slug": slug},
        )
        conn.execute(
            sa.text(
                "INSERT INTO organization_members (id, organization_id, user_id, role) "
                "VALUES (:id, :org_id, :user_id, 'owner')"
            ),
            {"id": uuid.uuid4(), "org_id": org_id, "user_id": user_id},
        )
        conn.execute(
            sa.text(
                "UPDATE projects SET organization_id = :org_id WHERE user_id = :user_id"
            ),
            {"org_id": org_id, "user_id": user_id},
        )


def downgrade() -> None:
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_column("projects", "organization_id")
    op.drop_index("ix_org_members_user_id", table_name="organization_members")
    op.drop_index("ix_org_members_org_id", table_name="organization_members")
    op.drop_table("organization_members")
    op.drop_table("organizations")

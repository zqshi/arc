"""add users table and ownership columns

Revision ID: i2k6gh589012
Revises: h1j5fg478901
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "i2k6gh589012"
down_revision = "h1j5fg478901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_users_username", "users", ["username"], unique=True,
        postgresql_where=sa.text("username IS NOT NULL"),
    )
    op.create_index(
        "idx_users_phone", "users", ["phone"], unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )

    op.create_table(
        "project_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(20), server_default="member", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members"),
    )

    op.add_column("projects", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_projects_user_id", "projects", "users", ["user_id"], ["id"])
    op.create_index("idx_projects_user_id", "projects", ["user_id"])

    op.add_column("todos", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_todos_user_id", "todos", "users", ["user_id"], ["id"])
    op.create_index("idx_todos_user_id", "todos", ["user_id"])

    op.add_column("experiences", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_experiences_user_id", "experiences", "users", ["user_id"], ["id"])
    op.create_index("idx_experiences_user_id", "experiences", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_experiences_user_id", table_name="experiences")
    op.drop_constraint("fk_experiences_user_id", "experiences", type_="foreignkey")
    op.drop_column("experiences", "user_id")

    op.drop_index("idx_todos_user_id", table_name="todos")
    op.drop_constraint("fk_todos_user_id", "todos", type_="foreignkey")
    op.drop_column("todos", "user_id")

    op.drop_index("idx_projects_user_id", table_name="projects")
    op.drop_constraint("fk_projects_user_id", "projects", type_="foreignkey")
    op.drop_column("projects", "user_id")

    op.drop_table("project_members")
    op.drop_table("users")

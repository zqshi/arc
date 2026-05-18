"""add projects, versions; upgrade todos and experiences

Revision ID: f9h3de256789
Revises: e8g2cd145678
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa

revision = "f9h3de256789"
down_revision = "e8g2cd145678"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tech_stack", sa.Text(), nullable=True),
        sa.Column("repo_url", sa.String(500), nullable=True),
        sa.Column("conventions", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="planning"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_versions_project_id", "versions", ["project_id"])

    # Upgrade todos
    op.add_column(
        "todos",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "todos",
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "todos",
        sa.Column("priority", sa.Integer(), server_default="2"),
    )
    op.create_index("ix_todos_project_id", "todos", ["project_id"])
    op.create_index("ix_todos_version_id", "todos", ["version_id"])

    # Upgrade experiences
    op.add_column(
        "experiences",
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_experiences_project_id", "experiences", ["project_id"])
    # Migrate old scope values
    op.execute("UPDATE experiences SET scope = 'personal' WHERE scope = 'global'")
    op.execute("UPDATE experiences SET scope = 'project' WHERE scope = 'todo'")


def downgrade() -> None:
    op.execute("UPDATE experiences SET scope = 'todo' WHERE scope = 'project' AND todo_id IS NOT NULL")
    op.execute("UPDATE experiences SET scope = 'global' WHERE scope = 'personal'")
    op.drop_index("ix_experiences_project_id", table_name="experiences")
    op.drop_column("experiences", "project_id")

    op.drop_index("ix_todos_version_id", table_name="todos")
    op.drop_index("ix_todos_project_id", table_name="todos")
    op.drop_column("todos", "priority")
    op.drop_column("todos", "version_id")
    op.drop_column("todos", "project_id")

    op.drop_index("ix_versions_project_id", table_name="versions")
    op.drop_table("versions")
    op.drop_table("projects")

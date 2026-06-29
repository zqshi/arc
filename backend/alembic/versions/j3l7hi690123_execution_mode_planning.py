"""add execution mode, planning engine tables, and deliverable tracker

Revision ID: j3l7hi690123
Revises: i2k6gh589012
Create Date: 2026-05-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "j3l7hi690123"
down_revision = "i2k6gh589012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Project: execution_mode + configs ---
    op.add_column("projects", sa.Column("execution_mode", sa.String(20), server_default="pipeline", nullable=False))
    op.add_column("projects", sa.Column("pipeline_config", JSONB, nullable=True))
    op.add_column("projects", sa.Column("conversation_config", JSONB, nullable=True))

    # --- Todo: execution_mode ---
    op.add_column("todos", sa.Column("execution_mode", sa.String(20), server_default="pipeline", nullable=False))

    # --- Artifact: phase_id nullable ---
    op.alter_column("artifacts", "phase_id", existing_type=sa.UUID(), nullable=True)

    # --- Documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(1000), server_default=""),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("parsed_features", JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default="uploading"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])

    # --- Planning Sessions ---
    op.create_table(
        "planning_sessions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_ids", JSONB, nullable=True),
        sa.Column("constraints", JSONB, nullable=True),
        sa.Column("roadmap", JSONB, nullable=True),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_planning_sessions_project_id", "planning_sessions", ["project_id"])

    # --- Deliverable Trackers ---
    op.create_table(
        "deliverable_trackers",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("todo_id", sa.UUID(), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("required", JSONB, nullable=True),
        sa.Column("deliverables", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("deliverable_trackers")
    op.drop_index("ix_planning_sessions_project_id", "planning_sessions")
    op.drop_table("planning_sessions")
    op.drop_index("ix_documents_project_id", "documents")
    op.drop_table("documents")
    op.alter_column("artifacts", "phase_id", existing_type=sa.UUID(), nullable=False)
    op.drop_column("todos", "execution_mode")
    op.drop_column("projects", "conversation_config")
    op.drop_column("projects", "pipeline_config")
    op.drop_column("projects", "execution_mode")

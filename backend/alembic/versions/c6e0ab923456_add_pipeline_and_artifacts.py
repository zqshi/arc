"""add pipeline_phases and artifacts tables, refactor todos

Revision ID: c6e0ab923456
Revises: b5d9fa812345
Create Date: 2026-05-16 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'c6e0ab923456'
down_revision: Union[str, None] = 'b5d9fa812345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add current_phase to todos
    op.add_column("todos", sa.Column("current_phase", sa.String(20), nullable=True))

    # 2. Create pipeline_phases table
    op.create_table(
        "pipeline_phases",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("todo_id", sa.UUID(), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("conversation_id", sa.UUID(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("todo_id", "phase_type", name="uq_pipeline_phases_todo_type"),
    )
    op.create_index("ix_pipeline_phases_todo_id", "pipeline_phases", ["todo_id"])

    # 3. Create artifacts table
    op.create_table(
        "artifacts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("todo_id", sa.UUID(), sa.ForeignKey("todos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase_id", sa.UUID(), sa.ForeignKey("pipeline_phases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_type", sa.String(30), nullable=False),
        sa.Column("content", sa.dialects.postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_artifacts_todo_id", "artifacts", ["todo_id"])
    op.create_index("ix_artifacts_phase_id", "artifacts", ["phase_id"])

    # 4. Migrate existing todo flat fields to artifacts
    # For each todo that has analyzing/dev/review/done status and has content in flat fields,
    # create a pipeline_phase + artifact with the requirement_spec data.
    op.execute("""
        INSERT INTO pipeline_phases (id, todo_id, phase_type, status, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            'clarification',
            CASE
                WHEN status = 'pending' THEN 'pending'
                ELSE 'confirmed'
            END,
            created_at,
            updated_at
        FROM todos
        WHERE background IS NOT NULL OR goals IS NOT NULL OR boundaries IS NOT NULL OR acceptance IS NOT NULL
    """)

    op.execute("""
        INSERT INTO artifacts (id, todo_id, phase_id, artifact_type, content, version, is_confirmed, confirmed_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            t.id,
            pp.id,
            'requirement_spec',
            jsonb_build_object(
                'background', COALESCE(t.background, ''),
                'goals', COALESCE(t.goals, ''),
                'boundaries', COALESCE(t.boundaries, ''),
                'acceptance_criteria', COALESCE(t.acceptance, '')
            ),
            1,
            CASE WHEN t.status != 'pending' THEN true ELSE false END,
            CASE WHEN t.status != 'pending' THEN t.updated_at ELSE NULL END,
            t.created_at,
            t.updated_at
        FROM todos t
        JOIN pipeline_phases pp ON pp.todo_id = t.id AND pp.phase_type = 'clarification'
    """)

    # Migrate tech_plan to architecture artifact if present
    op.execute("""
        INSERT INTO pipeline_phases (id, todo_id, phase_type, status, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            id,
            'architecture',
            CASE
                WHEN status IN ('dev', 'review', 'done') THEN 'confirmed'
                ELSE 'pending'
            END,
            created_at,
            updated_at
        FROM todos
        WHERE tech_plan IS NOT NULL AND tech_plan != ''
    """)

    op.execute("""
        INSERT INTO artifacts (id, todo_id, phase_id, artifact_type, content, version, is_confirmed, confirmed_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            t.id,
            pp.id,
            'tech_architecture',
            jsonb_build_object('architecture_overview', t.tech_plan),
            1,
            CASE WHEN t.status IN ('dev', 'review', 'done') THEN true ELSE false END,
            CASE WHEN t.status IN ('dev', 'review', 'done') THEN t.updated_at ELSE NULL END,
            t.created_at,
            t.updated_at
        FROM todos t
        JOIN pipeline_phases pp ON pp.todo_id = t.id AND pp.phase_type = 'architecture'
    """)

    # Map old status to new status + current_phase
    op.execute("UPDATE todos SET current_phase = 'clarification', status = 'active' WHERE status = 'analyzing'")
    op.execute("UPDATE todos SET current_phase = 'development', status = 'active' WHERE status = 'dev'")
    op.execute("UPDATE todos SET current_phase = 'testing', status = 'active' WHERE status = 'review'")
    op.execute("UPDATE todos SET status = 'done' WHERE status = 'done'")

    # 5. Drop old columns
    op.drop_column("todos", "background")
    op.drop_column("todos", "goals")
    op.drop_column("todos", "boundaries")
    op.drop_column("todos", "acceptance")
    op.drop_column("todos", "tech_plan")


def downgrade() -> None:
    # Re-add flat columns
    op.add_column("todos", sa.Column("background", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("goals", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("boundaries", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("acceptance", sa.Text(), nullable=True))
    op.add_column("todos", sa.Column("tech_plan", sa.Text(), nullable=True))

    # Migrate data back from artifacts
    op.execute("""
        UPDATE todos SET
            background = (a.content->>'background'),
            goals = (a.content->>'goals'),
            boundaries = (a.content->>'boundaries'),
            acceptance = (a.content->>'acceptance_criteria')
        FROM artifacts a
        JOIN pipeline_phases pp ON a.phase_id = pp.id
        WHERE pp.todo_id = todos.id AND a.artifact_type = 'requirement_spec'
    """)

    op.execute("""
        UPDATE todos SET
            tech_plan = (a.content->>'architecture_overview')
        FROM artifacts a
        JOIN pipeline_phases pp ON a.phase_id = pp.id
        WHERE pp.todo_id = todos.id AND a.artifact_type = 'tech_architecture'
    """)

    # Revert status values
    op.execute("UPDATE todos SET status = 'analyzing' WHERE status = 'active' AND current_phase = 'clarification'")
    op.execute("UPDATE todos SET status = 'dev' WHERE status = 'active' AND current_phase = 'development'")
    op.execute("UPDATE todos SET status = 'review' WHERE status = 'active' AND current_phase = 'testing'")

    op.drop_column("todos", "current_phase")
    op.drop_index("ix_artifacts_phase_id")
    op.drop_index("ix_artifacts_todo_id")
    op.drop_table("artifacts")
    op.drop_index("ix_pipeline_phases_todo_id")
    op.drop_table("pipeline_phases")

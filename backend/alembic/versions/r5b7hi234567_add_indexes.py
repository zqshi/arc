"""add indexes for frequently queried columns

Revision ID: r5b7hi234567
Revises: q4a6fg123456
"""

from alembic import op

revision = "r5b7hi234567"
down_revision = "q4a6fg123456"


def upgrade() -> None:
    op.create_index("ix_todos_user_id", "todos", ["user_id"], if_not_exists=True)
    op.create_index("ix_todos_project_id", "todos", ["project_id"], if_not_exists=True)
    op.create_index("ix_todos_version_id", "todos", ["version_id"], if_not_exists=True)
    op.create_index("ix_todos_status", "todos", ["status"], if_not_exists=True)
    op.create_index("ix_conversations_todo_id", "conversations", ["todo_id"], if_not_exists=True)
    op.create_index("ix_pipeline_phases_todo_id", "pipeline_phases", ["todo_id"], if_not_exists=True)
    op.create_index("ix_artifacts_todo_id", "artifacts", ["todo_id"], if_not_exists=True)
    op.create_index("ix_experiences_project_id", "experiences", ["project_id"], if_not_exists=True)
    op.create_index("ix_experiences_user_id", "experiences", ["user_id"], if_not_exists=True)
    op.create_index("ix_agent_sessions_todo_id", "agent_sessions", ["todo_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_agent_sessions_todo_id", "agent_sessions", if_exists=True)
    op.drop_index("ix_experiences_user_id", "experiences", if_exists=True)
    op.drop_index("ix_experiences_project_id", "experiences", if_exists=True)
    op.drop_index("ix_artifacts_todo_id", "artifacts", if_exists=True)
    op.drop_index("ix_pipeline_phases_todo_id", "pipeline_phases", if_exists=True)
    op.drop_index("ix_conversations_todo_id", "conversations", if_exists=True)
    op.drop_index("ix_todos_status", "todos", if_exists=True)
    op.drop_index("ix_todos_version_id", "todos", if_exists=True)
    op.drop_index("ix_todos_project_id", "todos", if_exists=True)
    op.drop_index("ix_todos_user_id", "todos", if_exists=True)

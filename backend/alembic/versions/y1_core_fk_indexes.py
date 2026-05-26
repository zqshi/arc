"""add core fk indexes on high-frequency query columns

Revision ID: y1_core_fk_indexes
Revises: x1_preview_url
"""

from alembic import op

revision = "y1_core_fk_indexes"
down_revision = "x1_preview_url"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_todos_user_id", "todos", ["user_id"]),
    ("ix_todos_project_id", "todos", ["project_id"]),
    ("ix_todos_version_id", "todos", ["version_id"]),
    ("ix_conversations_todo_id", "conversations", ["todo_id"]),
    ("ix_messages_conversation_id", "messages", ["conversation_id"]),
    ("ix_pipeline_phases_todo_id", "pipeline_phases", ["todo_id"]),
    ("ix_artifacts_todo_id", "artifacts", ["todo_id"]),
    ("ix_experiences_user_id", "experiences", ["user_id"]),
    ("ix_experiences_todo_id", "experiences", ["todo_id"]),
    ("ix_experiences_project_id", "experiences", ["project_id"]),
    ("ix_agent_sessions_todo_id", "agent_sessions", ["todo_id"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)

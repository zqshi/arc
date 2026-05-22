"""add missing foreign key indexes

Revision ID: u2v4_missing_fk_idx
Revises: t1t3_decay_distill
"""

from alembic import op

revision = "u2v4_missing_fk_idx"
down_revision = "t1t3_decay_distill"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_todo_deps_todo_id", "todo_dependencies", ["todo_id"]),
    ("ix_todo_deps_depends_on_id", "todo_dependencies", ["depends_on_id"]),
    ("ix_todos_source_session_id", "todos", ["source_session_id"]),
    ("ix_artifacts_phase_id", "artifacts", ["phase_id"]),
    ("ix_pipeline_phases_conversation_id", "pipeline_phases", ["conversation_id"]),
    ("ix_pipeline_phases_agent_session_id", "pipeline_phases", ["agent_session_id"]),
    ("ix_agent_sessions_phase_id", "agent_sessions", ["phase_id"]),
    ("ix_experiences_version_id", "experiences", ["version_id"]),
    ("ix_exp_feedback_todo_id", "experience_feedback", ["todo_id"]),
    ("ix_projects_user_id", "projects", ["user_id"]),
    ("ix_versions_project_id", "versions", ["project_id"]),
    ("ix_versions_parent_version_id", "versions", ["parent_version_id"]),
    ("ix_project_members_user_id", "project_members", ["user_id"]),
    ("ix_documents_project_id", "documents", ["project_id"]),
    ("ix_planning_sessions_project_id", "planning_sessions", ["project_id"]),
    ("ix_planning_sessions_version_id", "planning_sessions", ["version_id"]),
    ("ix_planning_sessions_conversation_id", "planning_sessions", ["conversation_id"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols, if_not_exists=True)


def downgrade() -> None:
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)

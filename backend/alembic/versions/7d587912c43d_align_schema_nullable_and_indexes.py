"""align_schema_nullable_and_indexes

ORM 模型从 Column() 迁移到 Mapped[] 时 nullable 语义变化，
以及部分索引命名调整。只做安全操作：nullable 收紧 + 索引重命名。
不删除任何已有索引（保留查询性能）。

Revision ID: 7d587912c43d
Revises: z4_experience_last_reused
Create Date: 2026-05-26 21:39:31.615623

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7d587912c43d'
down_revision: Union[str, None] = 'z4_experience_last_reused'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- nullable alignment (safe: all columns have server_default) --

    op.alter_column('agent_sessions', 'external_session_id',
               existing_type=sa.VARCHAR(length=255),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('agent_sessions', 'error_reason',
               existing_type=sa.TEXT(),
               nullable=False,
               existing_server_default=sa.text("''::text"))
    op.alter_column('agent_sessions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('agent_sessions', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('deliverable_trackers', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('deliverable_trackers', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('documents', 'storage_path',
               existing_type=sa.VARCHAR(length=1000),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('documents', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'uploading'::character varying"))
    op.alter_column('documents', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('documents', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('experience_feedback', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('experience_feedback', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('organization_members', 'role',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('organization_members', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('organizations', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('organizations', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('organizations', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('planning_sessions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'draft'::character varying"))
    op.alter_column('planning_sessions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('planning_sessions', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('projects', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'active'::character varying"))
    op.alter_column('projects', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('projects', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('revoked_tokens', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('todo_dependencies', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('todos', 'priority',
               existing_type=sa.INTEGER(),
               nullable=False,
               existing_server_default=sa.text('2'))

    op.alter_column('usage_daily', 'ai_calls',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('usage_daily', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    op.alter_column('versions', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False,
               existing_server_default=sa.text("'planning'::character varying"))
    op.alter_column('versions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))
    op.alter_column('versions', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False,
               existing_server_default=sa.text('now()'))

    # -- index renames (create new name, keep old for safety) --

    op.create_index(
        op.f('ix_organization_members_organization_id'),
        'organization_members', ['organization_id'],
        unique=False, if_not_exists=True)
    op.create_index(
        op.f('ix_organization_members_user_id'),
        'organization_members', ['user_id'],
        unique=False, if_not_exists=True)
    op.create_index(
        op.f('ix_todo_dependencies_depends_on_id'),
        'todo_dependencies', ['depends_on_id'],
        unique=False, if_not_exists=True)
    op.create_index(
        op.f('ix_todo_dependencies_todo_id'),
        'todo_dependencies', ['todo_id'],
        unique=False, if_not_exists=True)
    op.create_index(
        op.f('ix_usage_daily_organization_id'),
        'usage_daily', ['organization_id'],
        unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_usage_daily_organization_id'), table_name='usage_daily', if_exists=True)
    op.drop_index(op.f('ix_todo_dependencies_todo_id'), table_name='todo_dependencies', if_exists=True)
    op.drop_index(op.f('ix_todo_dependencies_depends_on_id'), table_name='todo_dependencies', if_exists=True)
    op.drop_index(op.f('ix_organization_members_user_id'), table_name='organization_members', if_exists=True)
    op.drop_index(op.f('ix_organization_members_organization_id'), table_name='organization_members', if_exists=True)

    for table, col, server_default in [
        ('versions', 'updated_at', "now()"),
        ('versions', 'created_at', "now()"),
        ('versions', 'status', "'planning'::character varying"),
        ('usage_daily', 'created_at', "now()"),
        ('todos', 'priority', "2"),
        ('todo_dependencies', 'created_at', "now()"),
        ('revoked_tokens', 'created_at', "now()"),
        ('projects', 'updated_at', "now()"),
        ('projects', 'created_at', "now()"),
        ('projects', 'status', "'active'::character varying"),
        ('planning_sessions', 'updated_at', "now()"),
        ('planning_sessions', 'created_at', "now()"),
        ('planning_sessions', 'status', "'draft'::character varying"),
        ('organizations', 'updated_at', "now()"),
        ('organizations', 'created_at', "now()"),
        ('experience_feedback', 'updated_at', "now()"),
        ('experience_feedback', 'created_at', "now()"),
        ('documents', 'updated_at', "now()"),
        ('documents', 'created_at', "now()"),
        ('documents', 'status', "'uploading'::character varying"),
        ('documents', 'storage_path', "''::character varying"),
        ('deliverable_trackers', 'updated_at', "now()"),
        ('deliverable_trackers', 'created_at', "now()"),
        ('agent_sessions', 'updated_at', "now()"),
        ('agent_sessions', 'created_at', "now()"),
        ('agent_sessions', 'error_reason', "''::text"),
        ('agent_sessions', 'external_session_id', "''::character varying"),
    ]:
        op.alter_column(table, col,
                   existing_type=postgresql.TIMESTAMP(timezone=True) if 'at' in col else sa.VARCHAR(),
                   nullable=True,
                   existing_server_default=sa.text(server_default))

    op.alter_column('usage_daily', 'ai_calls', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('organizations', 'is_active', existing_type=sa.BOOLEAN(), nullable=True)
    op.alter_column('organization_members', 'role', existing_type=sa.VARCHAR(length=20), nullable=True)

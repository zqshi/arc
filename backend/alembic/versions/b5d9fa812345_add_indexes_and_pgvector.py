"""add indexes and pgvector extension

Revision ID: b5d9fa812345
Revises: a4c8ba707264
Create Date: 2026-05-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'b5d9fa812345'
down_revision: Union[str, None] = 'a4c8ba707264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_index("ix_todos_status", "todos", ["status"])
    op.create_index("ix_todos_created_at", "todos", ["created_at"])
    op.create_index("ix_conversations_todo_id", "conversations", ["todo_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_experiences_todo_id", "experiences", ["todo_id"])

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_experiences_embedding_hnsw "
        "ON experiences USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_experiences_embedding_hnsw")
    op.drop_index("ix_experiences_todo_id")
    op.drop_index("ix_messages_created_at")
    op.drop_index("ix_messages_conversation_id")
    op.drop_index("ix_conversations_todo_id")
    op.drop_index("ix_todos_created_at")
    op.drop_index("ix_todos_status")

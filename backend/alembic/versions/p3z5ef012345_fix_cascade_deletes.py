"""fix cascade deletes for todo foreign keys

Revision ID: p3z5ef012345
Revises: n2y4cd890123
"""

from alembic import op

revision = "p3z5ef012345"
down_revision = "n2y4cd890123"


def upgrade() -> None:
    # conversations.todo_id
    op.drop_constraint("conversations_todo_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_todo_id_fkey", "conversations", "todos", ["todo_id"], ["id"], ondelete="CASCADE")

    # messages.conversation_id
    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key("messages_conversation_id_fkey", "messages", "conversations", ["conversation_id"], ["id"], ondelete="CASCADE")

    # experiences.todo_id
    op.drop_constraint("experiences_todo_id_fkey", "experiences", type_="foreignkey")
    op.create_foreign_key("experiences_todo_id_fkey", "experiences", "todos", ["todo_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    op.drop_constraint("experiences_todo_id_fkey", "experiences", type_="foreignkey")
    op.create_foreign_key("experiences_todo_id_fkey", "experiences", "todos", ["todo_id"], ["id"])

    op.drop_constraint("messages_conversation_id_fkey", "messages", type_="foreignkey")
    op.create_foreign_key("messages_conversation_id_fkey", "messages", "conversations", ["conversation_id"], ["id"])

    op.drop_constraint("conversations_todo_id_fkey", "conversations", type_="foreignkey")
    op.create_foreign_key("conversations_todo_id_fkey", "conversations", "todos", ["todo_id"], ["id"])

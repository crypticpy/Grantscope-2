"""Add tool_usage and metadata columns to chat tables.

Revision ID: 0013_chat_meta
Revises: 0012_sys_settings
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0013_chat_meta"
down_revision: Union[str, None] = "0012_sys_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ChatConversation columns
    op.add_column(
        "chat_conversations",
        sa.Column(
            "tool_usage",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )
    op.add_column(
        "chat_conversations",
        sa.Column(
            "metadata",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=True,
        ),
    )

    # ChatMessage columns
    op.add_column(
        "chat_messages",
        sa.Column("tool_calls", JSONB(), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("metadata", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "metadata")
    op.drop_column("chat_messages", "tool_calls")
    op.drop_column("chat_conversations", "metadata")
    op.drop_column("chat_conversations", "tool_usage")

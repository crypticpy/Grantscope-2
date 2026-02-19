"""Add grant_assistant to chat_conversations scope CHECK constraint.

The existing CHECK constraint only allows ('signal', 'workstream', 'global',
'wizard').  The Grant Discovery Assistant feature introduces a new scope
called 'grant_assistant' that must be added to the constraint.

Revision ID: 0014_ga_scope
Revises: 0013_chat_meta
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0014_ga_scope"
down_revision: Union[str, None] = "0013_chat_meta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chat_conversations "
        "DROP CONSTRAINT IF EXISTS chat_conversations_scope_check"
    )
    op.execute(
        "ALTER TABLE chat_conversations "
        "ADD CONSTRAINT chat_conversations_scope_check "
        "CHECK (scope IN ('signal', 'workstream', 'global', 'wizard', 'grant_assistant'))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE chat_conversations "
        "DROP CONSTRAINT IF EXISTS chat_conversations_scope_check"
    )
    op.execute(
        "ALTER TABLE chat_conversations "
        "ADD CONSTRAINT chat_conversations_scope_check "
        "CHECK (scope IN ('signal', 'workstream', 'global', 'wizard'))"
    )

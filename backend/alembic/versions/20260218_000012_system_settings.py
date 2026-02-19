"""Create system_settings table for admin-configurable feature flags.

Revision ID: 0012_sys_settings
Revises: 0011_card_docs
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0012_sys_settings"
down_revision: Union[str, None] = "0011_card_docs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column(
            "value",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Seed default settings
    op.execute(
        "INSERT INTO system_settings (key, value, description) VALUES "
        "('online_search_enabled', 'false', 'Allow AI assistant to search external sources'), "
        "('max_online_searches_per_turn', '3', 'Max external searches per chat turn'), "
        "('assistant_model', '\"gpt-4.1\"', 'Model deployment for assistant')"
    )


def downgrade() -> None:
    op.drop_table("system_settings")

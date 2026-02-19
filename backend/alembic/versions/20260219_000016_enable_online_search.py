"""Enable online search by default for expanded source access.

Sets the ``online_search_enabled`` system setting to ``true`` so that
chat tools can access Grants.gov, SAM.gov, web search, news, government
documents, and academic papers.

Revision ID: 0016_enable_online_search
Revises: 0015_hnsw_indexes
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0016_enable_online_search"
down_revision: Union[str, None] = "0015_hnsw_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable online search — uses upsert pattern in case the row already exists.
    # The value column is JSONB, so 'true' is stored as a JSON boolean string
    # matching the pattern used in the initial seed (migration 0012).
    op.execute(
        "INSERT INTO system_settings (key, value) "
        "VALUES ('online_search_enabled', 'true') "
        "ON CONFLICT (key) DO UPDATE SET value = 'true'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE system_settings SET value = 'false' "
        "WHERE key = 'online_search_enabled'"
    )

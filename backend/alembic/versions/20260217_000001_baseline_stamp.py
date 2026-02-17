"""Baseline stamp — existing schema from Supabase migrations.

This migration represents the starting point: all tables created by the 78
Supabase SQL migrations that were applied to Azure PostgreSQL via psql.
No DDL is executed here — we just stamp the revision so Alembic knows
where we are.

Revision ID: 0001_baseline
Revises: None
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Baseline stamp — no DDL.  The existing schema was applied via:
    #   bash infra/migrate.sh
    # which runs all 78 Supabase migration files through psql.
    pass


def downgrade() -> None:
    # Cannot undo the entire existing schema via Alembic.
    pass

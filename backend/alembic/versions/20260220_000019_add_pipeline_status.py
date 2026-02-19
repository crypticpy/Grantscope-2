"""Add pipeline_status columns to cards and workstreams.

Phase 1 of the pipeline lifecycle refactor (additive only).
Adds pipeline_status and pipeline_status_changed_at to cards, and
pipeline_statuses[] to workstreams for filter-level status tracking.

Revision ID: 0019_pipeline_status
Revises: 0018_admin_settings
Create Date: 2026-02-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_pipeline_status"
down_revision: Union[str, None] = "0018_admin_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- cards: pipeline lifecycle columns ------------------------------------
    op.add_column(
        "cards",
        sa.Column(
            "pipeline_status",
            sa.Text(),
            server_default="discovered",
            nullable=True,
        ),
    )
    op.add_column(
        "cards",
        sa.Column(
            "pipeline_status_changed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Backfill existing rows
    op.execute(
        "UPDATE cards SET pipeline_status = 'discovered' WHERE pipeline_status IS NULL"
    )

    # Index for filtering/grouping by pipeline status
    op.create_index("idx_cards_pipeline_status", "cards", ["pipeline_status"])

    # -- workstreams: pipeline status filter ----------------------------------
    op.add_column(
        "workstreams",
        sa.Column(
            "pipeline_statuses",
            sa.ARRAY(sa.Text()),
            server_default="{}",
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workstreams", "pipeline_statuses")
    op.drop_index("idx_cards_pipeline_status", table_name="cards")
    op.drop_column("cards", "pipeline_status_changed_at")
    op.drop_column("cards", "pipeline_status")

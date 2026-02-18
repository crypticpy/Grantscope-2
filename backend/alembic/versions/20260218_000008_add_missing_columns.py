"""Add columns that exist in the SQLAlchemy models but not in 001_complete_schema.

The database was created from 001_complete_schema.sql which uses array columns
(pillars TEXT[], goals TEXT[], anchors TEXT[]) and omits some columns from the
original numbered migrations (pillar_id, goal_id, anchor_id, stage_id,
maturity_score, risk_score, opportunity_score, last_updated).

The backend services extensively write to these columns, so we add them to the
database rather than refactoring ~20 service/router files.

Also adds the missing 'query' column to research_tasks (001_complete_schema
uses 'research_topic' but the model and worker reference 'query').

Revision ID: 0008_missing_cols
Revises: 0007_milestones
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_missing_cols"
down_revision: Union[str, None] = "0007_milestones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- cards: FK columns that the original numbered migrations had ----------
    op.add_column(
        "cards",
        sa.Column("pillar_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column("goal_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column("anchor_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column("stage_id", sa.Text(), nullable=True),
    )

    # -- cards: score columns -------------------------------------------------
    op.add_column(
        "cards",
        sa.Column("maturity_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column("risk_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cards",
        sa.Column("opportunity_score", sa.Integer(), nullable=True),
    )

    # -- cards: last_updated timestamp ----------------------------------------
    op.add_column(
        "cards",
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    # -- research_tasks: query column -----------------------------------------
    op.add_column(
        "research_tasks",
        sa.Column("query", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_tasks", "query")
    op.drop_column("cards", "last_updated")
    op.drop_column("cards", "opportunity_score")
    op.drop_column("cards", "risk_score")
    op.drop_column("cards", "maturity_score")
    op.drop_column("cards", "stage_id")
    op.drop_column("cards", "anchor_id")
    op.drop_column("cards", "goal_id")
    op.drop_column("cards", "pillar_id")

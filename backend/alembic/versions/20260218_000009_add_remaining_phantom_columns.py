"""Add remaining columns that exist in SQLAlchemy models but not in DB.

Continuation of 0008: fixes phantom columns across card_follows,
card_timeline, entities, sources, and workstreams. Also creates the
classification_validations table.

Revision ID: 0009_phantom_cols
Revises: 0008_missing_cols
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

revision: str = "0009_phantom_cols"
down_revision: Union[str, None] = "0008_missing_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- card_follows: priority and notes ------------------------------------
    op.add_column(
        "card_follows",
        sa.Column("priority", sa.Text(), server_default="medium", nullable=True),
    )
    op.add_column("card_follows", sa.Column("notes", sa.Text(), nullable=True))

    # -- card_timeline: title, description, created_by -----------------------
    op.add_column("card_timeline", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("card_timeline", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "card_timeline", sa.Column("created_by", UUID(as_uuid=True), nullable=True)
    )

    # -- entities: context, canonical_name, embedding ------------------------
    op.add_column("entities", sa.Column("context", sa.Text(), nullable=True))
    op.add_column("entities", sa.Column("canonical_name", sa.Text(), nullable=True))
    op.add_column("entities", sa.Column("embedding", Vector(1536), nullable=True))

    # -- sources: content, summary, source_type, publisher, dates ------------
    op.add_column("sources", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("source_type", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("publisher", sa.Text(), nullable=True))
    op.add_column(
        "sources",
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sources", sa.Column("fetched_date", sa.DateTime(timezone=True), nullable=True)
    )

    # -- workstreams: legacy filter columns ----------------------------------
    op.add_column(
        "workstreams",
        sa.Column(
            "pillar_ids", sa.ARRAY(sa.Text()), server_default="{}", nullable=True
        ),
    )
    op.add_column(
        "workstreams",
        sa.Column("goal_ids", sa.ARRAY(sa.Text()), server_default="{}", nullable=True),
    )
    op.add_column(
        "workstreams",
        sa.Column("stage_ids", sa.ARRAY(sa.Text()), server_default="{}", nullable=True),
    )
    op.add_column("workstreams", sa.Column("horizon", sa.Text(), nullable=True))
    op.add_column(
        "workstreams",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=True),
    )
    op.add_column(
        "workstreams",
        sa.Column("auto_add", sa.Boolean(), server_default="false", nullable=True),
    )

    # -- classification_validations table ------------------------------------
    op.create_table(
        "classification_validations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("card_id", UUID(as_uuid=True), nullable=False),
        sa.Column("predicted_pillar", sa.Text(), nullable=False),
        sa.Column("ground_truth_pillar", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence_at_prediction", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("classification_validations")

    op.drop_column("workstreams", "auto_add")
    op.drop_column("workstreams", "is_active")
    op.drop_column("workstreams", "horizon")
    op.drop_column("workstreams", "stage_ids")
    op.drop_column("workstreams", "goal_ids")
    op.drop_column("workstreams", "pillar_ids")

    op.drop_column("sources", "fetched_date")
    op.drop_column("sources", "published_date")
    op.drop_column("sources", "publisher")
    op.drop_column("sources", "source_type")
    op.drop_column("sources", "summary")
    op.drop_column("sources", "content")

    op.drop_column("entities", "embedding")
    op.drop_column("entities", "canonical_name")
    op.drop_column("entities", "context")

    op.drop_column("card_timeline", "created_by")
    op.drop_column("card_timeline", "description")
    op.drop_column("card_timeline", "title")

    op.drop_column("card_follows", "notes")
    op.drop_column("card_follows", "priority")

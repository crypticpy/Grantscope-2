"""Add user profile wizard columns.

Adds 16 columns to the ``users`` table to support the profile setup wizard:
bio, program details, grant preferences, strategic pillars, priorities,
and wizard progress tracking.

Revision ID: 0010_profile_cols
Revises: 0009_phantom_cols
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_profile_cols"
down_revision: Union[str, None] = "0009_phantom_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("program_name", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("program_mission", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("team_size", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("budget_range", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("grant_experience", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "grant_categories", sa.ARRAY(sa.Text()), server_default="{}", nullable=True
        ),
    )
    op.add_column("users", sa.Column("funding_range_min", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("funding_range_max", sa.Integer(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "strategic_pillars", sa.ARRAY(sa.Text()), server_default="{}", nullable=True
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "priorities", sa.ARRAY(sa.Text()), server_default="{}", nullable=True
        ),
    )
    op.add_column("users", sa.Column("custom_priorities", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "help_wanted", sa.ARRAY(sa.Text()), server_default="{}", nullable=True
        ),
    )
    op.add_column("users", sa.Column("update_frequency", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("profile_step", sa.Integer(), server_default="0", nullable=True),
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_column("users", "profile_step")
    op.drop_column("users", "profile_completed_at")
    op.drop_column("users", "update_frequency")
    op.drop_column("users", "help_wanted")
    op.drop_column("users", "custom_priorities")
    op.drop_column("users", "priorities")
    op.drop_column("users", "strategic_pillars")
    op.drop_column("users", "funding_range_max")
    op.drop_column("users", "funding_range_min")
    op.drop_column("users", "grant_categories")
    op.drop_column("users", "grant_experience")
    op.drop_column("users", "budget_range")
    op.drop_column("users", "team_size")
    op.drop_column("users", "program_mission")
    op.drop_column("users", "program_name")
    op.drop_column("users", "bio")

"""Create application_milestones and application_status_history tables.

Revision ID: 0007_milestones
Revises: 0006_collaboration
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0007_milestones"
down_revision: Union[str, None] = "0006_collaboration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- application_milestones ---
    op.create_table(
        "application_milestones",
        sa.Column(
            "id",
            UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            UUID(),
            sa.ForeignKey("grant_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "milestone_type",
            sa.Text(),
            server_default="custom",
            nullable=False,
        ),
        sa.Column("reminder_sent", sa.Boolean(), server_default="false", nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "milestone_type IN ('deadline','loi','draft_review','internal_review',"
            "'submission','reporting','custom')",
            name="application_milestones_type_check",
        ),
    )
    op.create_index("idx_milestones_app", "application_milestones", ["application_id"])
    # Partial index for upcoming milestones
    op.execute(
        "CREATE INDEX idx_milestones_due ON application_milestones(due_date) "
        "WHERE NOT is_completed"
    )

    # --- application_status_history ---
    op.create_table(
        "application_status_history",
        sa.Column(
            "id",
            UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "application_id",
            UUID(),
            sa.ForeignKey("grant_applications.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_status", sa.Text(), nullable=True),
        sa.Column("new_status", sa.Text(), nullable=False),
        sa.Column(
            "changed_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_status_history_app",
        "application_status_history",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_status_history_app", table_name="application_status_history")
    op.drop_table("application_status_history")
    op.execute("DROP INDEX IF EXISTS idx_milestones_due")
    op.drop_index("idx_milestones_app", table_name="application_milestones")
    op.drop_table("application_milestones")

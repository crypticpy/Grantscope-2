"""Create checklist_items table for application materials tracking.

Revision ID: 0003_checklist
Revises: 0002_enhance_apps
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003_checklist"
down_revision: Union[str, None] = "0002_enhance_apps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "checklist_items",
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
        sa.Column(
            "category",
            sa.Text(),
            server_default="other",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "completed_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("attachment_id", UUID(), nullable=True),  # FK added later
        sa.Column(
            "source",
            sa.Text(),
            server_default="extracted",
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sub_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            "category IN ('narrative','budget','timeline','evaluation',"
            "'organizational','staffing','legal','registration','other')",
            name="checklist_items_category_check",
        ),
        sa.CheckConstraint(
            "source IN ('extracted','ai_suggested','user_added')",
            name="checklist_items_source_check",
        ),
    )
    op.create_index("idx_checklist_app", "checklist_items", ["application_id"])
    op.create_index(
        "idx_checklist_status",
        "checklist_items",
        ["application_id", "is_completed"],
    )


def downgrade() -> None:
    op.drop_index("idx_checklist_status", table_name="checklist_items")
    op.drop_index("idx_checklist_app", table_name="checklist_items")
    op.drop_table("checklist_items")

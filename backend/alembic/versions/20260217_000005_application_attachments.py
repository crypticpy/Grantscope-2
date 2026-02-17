"""Create application_attachments table and link to checklist_items.

Revision ID: 0005_attachments
Revises: 0004_budget
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0005_attachments"
down_revision: Union[str, None] = "0004_budget"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "application_attachments",
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
            "checklist_item_id",
            UUID(),
            sa.ForeignKey("checklist_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("blob_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.Text(), server_default="other", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "uploaded_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("ai_extracted_data", JSONB(), nullable=True),
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
            "category IN ('narrative','budget_form','letter_of_support','org_chart',"
            "'resume','audit_report','registration_proof','indirect_rate_agreement',"
            "'data_management_plan','other')",
            name="application_attachments_category_check",
        ),
    )
    op.create_index(
        "idx_attachments_app", "application_attachments", ["application_id"]
    )
    op.create_index(
        "idx_attachments_checklist",
        "application_attachments",
        ["checklist_item_id"],
    )

    # Add FK from checklist_items.attachment_id -> application_attachments.id
    op.create_foreign_key(
        "fk_checklist_attachment",
        "checklist_items",
        "application_attachments",
        ["attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_checklist_attachment", "checklist_items", type_="foreignkey")
    op.drop_index("idx_attachments_checklist", table_name="application_attachments")
    op.drop_index("idx_attachments_app", table_name="application_attachments")
    op.drop_table("application_attachments")

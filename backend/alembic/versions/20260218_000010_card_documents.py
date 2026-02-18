"""Create card_documents table for uploading documents to cards.

Revision ID: 0011_card_docs
Revises: 0010_profile_cols
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0011_card_docs"
down_revision: Union[str, None] = "0010_profile_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_documents",
        sa.Column(
            "id",
            UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "card_id",
            UUID(),
            sa.ForeignKey("cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("blob_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "extraction_status",
            sa.Text(),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "document_type",
            sa.Text(),
            server_default="other",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'::jsonb")),
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
            "extraction_status IN ('pending', 'completed', 'failed')",
            name="card_documents_extraction_status_check",
        ),
        sa.CheckConstraint(
            "document_type IN ('nofo', 'budget', 'narrative', "
            "'letter_of_support', 'application_guide', 'other')",
            name="card_documents_document_type_check",
        ),
    )
    op.create_index("idx_card_documents_card_id", "card_documents", ["card_id"])
    op.create_index("idx_card_documents_uploaded_by", "card_documents", ["uploaded_by"])

    # Enable RLS
    op.execute("ALTER TABLE card_documents ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY card_documents_authenticated_select ON card_documents "
        "FOR SELECT TO authenticated USING (true)"
    )
    op.execute(
        "CREATE POLICY card_documents_authenticated_insert ON card_documents "
        "FOR INSERT TO authenticated WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY card_documents_authenticated_delete ON card_documents "
        "FOR DELETE TO authenticated USING (uploaded_by = auth.uid())"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS card_documents_authenticated_delete ON card_documents"
    )
    op.execute(
        "DROP POLICY IF EXISTS card_documents_authenticated_insert ON card_documents"
    )
    op.execute(
        "DROP POLICY IF EXISTS card_documents_authenticated_select ON card_documents"
    )
    op.drop_index("idx_card_documents_uploaded_by", table_name="card_documents")
    op.drop_index("idx_card_documents_card_id", table_name="card_documents")
    op.drop_table("card_documents")

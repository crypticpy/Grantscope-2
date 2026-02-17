"""Create collaboration tables: collaborators, comments.

Revision ID: 0006_collaboration
Revises: 0005_attachments
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0006_collaboration"
down_revision: Union[str, None] = "0005_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- application_collaborators ---
    op.create_table(
        "application_collaborators",
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
            "user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), server_default="viewer", nullable=False),
        sa.Column(
            "invited_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "invited_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("application_id", "user_id", name="uq_collab_app_user"),
        sa.CheckConstraint(
            "role IN ('owner','editor','reviewer','viewer')",
            name="application_collaborators_role_check",
        ),
    )
    op.create_index("idx_collab_user", "application_collaborators", ["user_id"])

    # --- application_comments ---
    op.create_table(
        "application_comments",
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
            "proposal_id",
            UUID(),
            sa.ForeignKey("proposals.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("section_name", sa.Text(), nullable=True),
        sa.Column(
            "parent_id",
            UUID(),
            sa.ForeignKey("application_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "author_id",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "resolved_by",
            UUID(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("idx_comments_app", "application_comments", ["application_id"])
    op.create_index(
        "idx_comments_section",
        "application_comments",
        ["proposal_id", "section_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_comments_section", table_name="application_comments")
    op.drop_index("idx_comments_app", table_name="application_comments")
    op.drop_table("application_comments")
    op.drop_index("idx_collab_user", table_name="application_collaborators")
    op.drop_table("application_collaborators")

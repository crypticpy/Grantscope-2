"""Create budget_line_items and budget_settings tables.

Revision ID: 0004_budget
Revises: 0003_checklist
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0004_budget"
down_revision: Union[str, None] = "0003_checklist"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- budget_line_items ---
    op.create_table(
        "budget_line_items",
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
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        # Personnel-specific
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("fte", sa.Numeric(4, 2), nullable=True),
        sa.Column("annual_salary", sa.Numeric(12, 2), nullable=True),
        sa.Column("months_on_project", sa.Numeric(4, 1), nullable=True),
        # General
        sa.Column("quantity", sa.Numeric(10, 2), server_default="1", nullable=True),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        # Match/cost-share
        sa.Column("federal_share", sa.Numeric(12, 2), nullable=True),
        sa.Column("match_share", sa.Numeric(12, 2), nullable=True),
        sa.Column("match_type", sa.Text(), nullable=True),
        # Metadata
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_indirect", sa.Boolean(), server_default="false", nullable=False),
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
            "category IN ('personnel','fringe_benefits','travel','equipment',"
            "'supplies','contractual','construction','other_direct','indirect_costs')",
            name="budget_line_items_category_check",
        ),
        sa.CheckConstraint(
            "match_type IN ('cash','in_kind') OR match_type IS NULL",
            name="budget_line_items_match_type_check",
        ),
    )
    op.create_index("idx_budget_app", "budget_line_items", ["application_id"])
    op.create_index(
        "idx_budget_category",
        "budget_line_items",
        ["application_id", "category"],
    )

    # --- budget_settings ---
    op.create_table(
        "budget_settings",
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
            unique=True,
        ),
        sa.Column(
            "fringe_rate",
            sa.Numeric(5, 4),
            server_default="0.3500",
            nullable=True,
        ),
        sa.Column(
            "indirect_rate",
            sa.Numeric(5, 4),
            server_default="0.1000",
            nullable=True,
        ),
        sa.Column(
            "indirect_base",
            sa.Text(),
            server_default="mtdc",
            nullable=True,
        ),
        sa.Column(
            "match_required", sa.Boolean(), server_default="false", nullable=True
        ),
        sa.Column("match_percentage", sa.Numeric(5, 4), nullable=True),
        sa.Column("match_total_required", sa.Numeric(12, 2), nullable=True),
        sa.Column("fiscal_year_start", sa.Text(), nullable=True),
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
            "indirect_base IN ('mtdc','tdc','salary_wages')",
            name="budget_settings_indirect_base_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("budget_settings")
    op.drop_index("idx_budget_category", table_name="budget_line_items")
    op.drop_index("idx_budget_app", table_name="budget_line_items")
    op.drop_table("budget_line_items")

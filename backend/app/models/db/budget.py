"""SQLAlchemy models for budget_line_items and budget_settings tables."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BudgetLineItem(Base):
    __tablename__ = "budget_line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grant_applications.id", ondelete="CASCADE"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Personnel-specific
    role: Mapped[str | None] = mapped_column(Text, nullable=True)
    fte: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    annual_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    months_on_project: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 1), nullable=True
    )

    # General
    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), server_default="1", nullable=True
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Match/cost-share
    federal_share: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    match_share: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    match_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    is_indirect: Mapped[bool] = mapped_column(
        Boolean, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BudgetSettings(Base):
    __tablename__ = "budget_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("grant_applications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    fringe_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), server_default="0.3500", nullable=True
    )
    indirect_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), server_default="0.1000", nullable=True
    )
    indirect_base: Mapped[str | None] = mapped_column(
        Text, server_default="mtdc", nullable=True
    )
    match_required: Mapped[bool | None] = mapped_column(
        Boolean, server_default="false", nullable=True
    )
    match_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    match_total_required: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    fiscal_year_start: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

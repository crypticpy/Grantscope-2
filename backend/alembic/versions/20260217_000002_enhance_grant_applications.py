"""Enhance grant_applications and proposals for application pipeline.

Adds new columns to grant_applications for full lifecycle tracking,
and extends proposals with custom sections and approval tracking.

Revision ID: 0002_enhance_apps
Revises: 0001_baseline
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa  # noqa: F401

revision: str = "0002_enhance_apps"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- grant_applications enhancements ---
    # Use raw SQL with IF NOT EXISTS for columns that may already exist from Supabase migrations
    op.execute("ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS title TEXT")
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS progress_pct INTEGER DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS decision_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS submission_portal TEXT"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS submission_confirmation TEXT"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS reporting_deadline TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS internal_deadline TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD COLUMN IF NOT EXISTS wizard_session_id UUID"
    )

    # FK for wizard_session_id (idempotent)
    op.execute(
        "DO $$ BEGIN "
        "ALTER TABLE grant_applications ADD CONSTRAINT fk_grant_app_wizard_session "
        "FOREIGN KEY (wizard_session_id) REFERENCES wizard_sessions(id); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # Expand status check constraint
    op.execute(
        "ALTER TABLE grant_applications "
        "DROP CONSTRAINT IF EXISTS grant_applications_status_check"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD CONSTRAINT grant_applications_status_check "
        "CHECK (status IN ("
        "'draft','in_progress','under_review','submitted',"
        "'pending_decision','awarded','declined','withdrawn','expired'"
        "))"
    )

    # --- proposals enhancements ---
    op.execute(
        "ALTER TABLE proposals ADD COLUMN IF NOT EXISTS custom_sections JSONB DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE proposals ADD COLUMN IF NOT EXISTS word_counts JSONB DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE proposals ADD COLUMN IF NOT EXISTS section_approvals JSONB DEFAULT '{}'::jsonb"
    )


def downgrade() -> None:
    # proposals
    op.drop_column("proposals", "section_approvals")
    op.drop_column("proposals", "word_counts")
    op.drop_column("proposals", "custom_sections")

    # grant_applications
    op.drop_constraint(
        "fk_grant_app_wizard_session", "grant_applications", type_="foreignkey"
    )
    op.drop_column("grant_applications", "wizard_session_id")
    op.drop_column("grant_applications", "internal_deadline")
    op.drop_column("grant_applications", "reporting_deadline")
    op.drop_column("grant_applications", "submission_confirmation")
    op.drop_column("grant_applications", "submission_portal")
    op.drop_column("grant_applications", "decision_at")
    op.drop_column("grant_applications", "submitted_at")
    op.drop_column("grant_applications", "progress_pct")
    op.drop_column("grant_applications", "title")

    # Restore original status constraint
    op.execute(
        "ALTER TABLE grant_applications "
        "DROP CONSTRAINT IF EXISTS grant_applications_status_check"
    )
    op.execute(
        "ALTER TABLE grant_applications ADD CONSTRAINT grant_applications_status_check "
        "CHECK (status IN ('draft','in_progress','submitted','awarded','declined','withdrawn'))"
    )

"""Add card_analysis and workstream_analysis to research_tasks task_type check.

The original CHECK constraint only allowed: update, research_topic,
workstream_scan, refresh_summary, deep_research.  This adds card_analysis
(automatic AI analysis on card creation) and workstream_analysis.

Revision ID: 0017_card_analysis_type
Revises: 0016_enable_online_search
Create Date: 2026-02-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0017_card_analysis_type"
down_revision: Union[str, None] = "0016_enable_online_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE research_tasks DROP CONSTRAINT IF EXISTS research_tasks_task_type_check"
    )
    op.execute(
        "ALTER TABLE research_tasks ADD CONSTRAINT research_tasks_task_type_check "
        "CHECK (task_type = ANY (ARRAY["
        "'update'::text, 'research_topic'::text, 'workstream_scan'::text, "
        "'refresh_summary'::text, 'deep_research'::text, "
        "'workstream_analysis'::text, 'card_analysis'::text"
        "]))"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE research_tasks DROP CONSTRAINT IF EXISTS research_tasks_task_type_check"
    )
    op.execute(
        "ALTER TABLE research_tasks ADD CONSTRAINT research_tasks_task_type_check "
        "CHECK (task_type = ANY (ARRAY["
        "'update'::text, 'research_topic'::text, 'workstream_scan'::text, "
        "'refresh_summary'::text, 'deep_research'::text"
        "]))"
    )

"""Seed all admin-configurable settings into system_settings.

Populates system_settings with defaults for search, AI, discovery pipeline,
worker, scheduler, content management, quality scoring, RSS, and rate limits.
Uses ON CONFLICT DO NOTHING so existing overrides are preserved.

Revision ID: 0018_admin_settings
Revises: 0017_card_analysis_type
Create Date: 2026-02-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_admin_settings"
down_revision: Union[str, None] = "0017_card_analysis_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (key, value_json, description)
SETTINGS: list[tuple[str, str, str]] = [
    # Search & Sources
    ("search_provider", '"auto"', "Search provider: auto, searxng, serper, tavily"),
    (
        "source_toggles",
        '{"grants_gov":true,"sam_gov":true,"web":true,"news":true,"government":true,"academic":false}',
        "Enabled source categories for multi-source search",
    ),
    (
        "rrf_weights",
        '{"grants_gov":1.5,"sam_gov":1.5,"government":1.2,"web":1.0,"news":0.8,"academic":0.6}',
        "RRF reranking source weights",
    ),
    (
        "dedup_thresholds",
        '{"duplicate":0.95,"card_dedup":0.92,"related":0.85}',
        "Deduplication similarity thresholds",
    ),
    # AI Configuration
    ("chat_temperature", "0.7", "Chat LLM temperature (0.0-2.0)"),
    ("chat_max_tokens", "8192", "Chat max output tokens"),
    ("chat_max_tool_rounds", "3", "Max tool-calling rounds per chat turn"),
    ("chat_rate_limit_per_minute", "20", "Per-user chat rate limit"),
    # Discovery Pipeline
    ("discovery_max_queries", "100", "Max queries per discovery run"),
    ("discovery_max_sources_per_query", "10", "Sources per query in discovery"),
    ("discovery_max_sources_total", "500", "Total source cap per discovery run"),
    ("discovery_auto_approve_threshold", "0.95", "Auto-approve confidence threshold"),
    ("discovery_max_new_cards_per_run", "15", "Max new cards per discovery run"),
    # Worker Configuration
    ("worker_poll_interval", "5.0", "Worker base poll interval in seconds"),
    ("worker_max_poll_interval", "30.0", "Worker max backoff interval in seconds"),
    # Scheduler Job Toggles
    (
        "scheduler_jobs",
        '{"enrich_thin_descriptions":true,"scheduled_workstream_scans":true,"nightly_reputation_aggregation":true,"nightly_scan":true,"nightly_sqi_recalculation":true,"weekly_discovery":true,"nightly_pattern_detection":true,"nightly_velocity_calculation":true,"daily_digest_batch":true,"scan_grants":true}',
        "Per-job enable/disable toggles",
    ),
    # Content Management
    (
        "card_retention_days",
        "365",
        "Days before inactive cards auto-archive (0=disabled)",
    ),
    ("nightly_scan_max_cards", "20", "Max cards per nightly content scan"),
    (
        "nightly_scan_staleness_hours",
        "48",
        "Hours before a card is considered stale for scanning",
    ),
    (
        "enrichment_threshold_chars",
        "1600",
        "Description length threshold for enrichment",
    ),
    ("enrichment_max_cards_per_run", "500", "Max cards per enrichment batch"),
    # Quality Scoring
    (
        "signal_quality_weights",
        '{"source_count":0.15,"source_diversity":0.10,"avg_credibility":0.15,"avg_triage_confidence":0.10,"deep_research":0.15,"research_tasks":0.10,"entity_count":0.05,"human_review":0.10,"engagement":0.10}',
        "Signal quality component weights (must sum to 1.0)",
    ),
    # RSS Configuration
    ("rss_max_error_count", "5", "Consecutive errors before RSS feed is disabled"),
    (
        "rss_default_check_interval_hours",
        "6",
        "Default RSS feed check interval in hours",
    ),
    # Rate Limits
    ("research_deep_limit_per_day", "2", "Deep research tasks per card per day"),
    ("workstream_scan_limit_per_day", "2", "Workstream scans per workstream per day"),
]


def upgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        "INSERT INTO system_settings (key, value, description) "
        "VALUES (:key, :value::jsonb, :description) "
        "ON CONFLICT (key) DO NOTHING"
    )
    for key, value, description in SETTINGS:
        conn.execute(stmt, {"key": key, "value": value, "description": description})


def downgrade() -> None:
    conn = op.get_bind()
    all_keys = [k for k, _, _ in SETTINGS]
    conn.execute(
        sa.text("DELETE FROM system_settings WHERE key = ANY(:keys)"),
        {"keys": all_keys},
    )

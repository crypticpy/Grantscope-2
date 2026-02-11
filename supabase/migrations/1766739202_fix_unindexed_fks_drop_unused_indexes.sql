-- ==========================================================================
-- Fix unindexed foreign keys + drop unused indexes
--
-- 1. unindexed_foreign_keys (16) — Add covering indexes on FK columns
--    to prevent sequential scans on JOINs and cascading deletes.
--
-- 2. unused_index (~30) — Drop indexes that have never been used since
--    stats collection began.  They add write overhead with no read benefit.
--    All can be recreated cheaply if query patterns change.
-- ==========================================================================

BEGIN;

-- =========================================================================
-- 1. ADD MISSING FOREIGN KEY INDEXES
-- =========================================================================

CREATE INDEX IF NOT EXISTS idx_card_follows_card_id
    ON public.card_follows (card_id);

CREATE INDEX IF NOT EXISTS idx_card_notes_card_id
    ON public.card_notes (card_id);

CREATE INDEX IF NOT EXISTS idx_card_notes_user_id
    ON public.card_notes (user_id);

CREATE INDEX IF NOT EXISTS idx_card_timeline_created_by
    ON public.card_timeline (created_by);

CREATE INDEX IF NOT EXISTS idx_cards_anchor_id
    ON public.cards (anchor_id);

CREATE INDEX IF NOT EXISTS idx_cards_created_by
    ON public.cards (created_by);

CREATE INDEX IF NOT EXISTS idx_cards_goal_id
    ON public.cards (goal_id);

CREATE INDEX IF NOT EXISTS idx_cards_pillar_id
    ON public.cards (pillar_id);

CREATE INDEX IF NOT EXISTS idx_cards_rejected_by
    ON public.cards (rejected_by);

CREATE INDEX IF NOT EXISTS idx_cards_stage_id
    ON public.cards (stage_id);

CREATE INDEX IF NOT EXISTS idx_discovery_runs_triggered_by_user
    ON public.discovery_runs (triggered_by_user);

CREATE INDEX IF NOT EXISTS idx_goals_pillar_id
    ON public.goals (pillar_id);

CREATE INDEX IF NOT EXISTS idx_sources_card_id
    ON public.sources (card_id);

CREATE INDEX IF NOT EXISTS idx_workstream_cards_added_by
    ON public.workstream_cards (added_by);

CREATE INDEX IF NOT EXISTS idx_workstream_cards_card_id
    ON public.workstream_cards (card_id);

CREATE INDEX IF NOT EXISTS idx_workstreams_user_id
    ON public.workstreams (user_id);


-- =========================================================================
-- 2. DROP UNUSED INDEXES
-- =========================================================================

-- research_tasks
DROP INDEX IF EXISTS idx_research_tasks_user_created;

-- domain_reputation
DROP INDEX IF EXISTS idx_domain_reputation_pattern;
DROP INDEX IF EXISTS idx_domain_reputation_tier;
DROP INDEX IF EXISTS idx_domain_reputation_composite;
DROP INDEX IF EXISTS idx_domain_reputation_category;

-- entities
DROP INDEX IF EXISTS idx_entities_card;

-- cards
DROP INDEX IF EXISTS idx_cards_top25;
DROP INDEX IF EXISTS idx_cards_origin;
DROP INDEX IF EXISTS idx_cards_exploratory;
DROP INDEX IF EXISTS idx_cards_reviewed_at;
DROP INDEX IF EXISTS idx_cards_reviewed_by;
DROP INDEX IF EXISTS idx_cards_auto_approved_at;
DROP INDEX IF EXISTS idx_cards_discovered_at;
DROP INDEX IF EXISTS idx_cards_pending_review;

-- source_ratings
DROP INDEX IF EXISTS idx_source_ratings_source;
DROP INDEX IF EXISTS idx_source_ratings_user;
DROP INDEX IF EXISTS idx_source_ratings_quality;

-- sources
DROP INDEX IF EXISTS idx_sources_peer_reviewed;
DROP INDEX IF EXISTS idx_sources_story_cluster;
DROP INDEX IF EXISTS idx_sources_domain_reputation;

-- user_signal_preferences
DROP INDEX IF EXISTS idx_user_signal_prefs_user;
DROP INDEX IF EXISTS idx_user_signal_prefs_card;
DROP INDEX IF EXISTS idx_user_signal_prefs_pinned;

-- discovery_blocks
DROP INDEX IF EXISTS idx_discovery_blocks_embedding;
DROP INDEX IF EXISTS idx_discovery_blocks_keywords;

-- user_card_dismissals
DROP INDEX IF EXISTS idx_user_dismissals_user;
DROP INDEX IF EXISTS idx_user_dismissals_user_dismissed;

-- discovered_sources
DROP INDEX IF EXISTS idx_discovered_sources_url;
DROP INDEX IF EXISTS idx_discovered_sources_status;
DROP INDEX IF EXISTS idx_discovered_sources_pillar;
DROP INDEX IF EXISTS idx_discovered_sources_embedding;

-- workstream_cards
DROP INDEX IF EXISTS idx_workstream_cards_status;
DROP INDEX IF EXISTS idx_workstream_cards_reminder;

-- card_score_history
DROP INDEX IF EXISTS idx_card_score_history_card_id_recorded_at;

-- executive_briefs
DROP INDEX IF EXISTS idx_executive_briefs_card;
DROP INDEX IF EXISTS idx_executive_briefs_status;
DROP INDEX IF EXISTS idx_executive_briefs_created_by;
DROP INDEX IF EXISTS idx_executive_briefs_workstream_card_version;

-- saved_searches
DROP INDEX IF EXISTS idx_saved_searches_user_id;

-- search_history
DROP INDEX IF EXISTS idx_search_history_user_id;

-- cached_insights
DROP INDEX IF EXISTS idx_cached_insights_lookup;
DROP INDEX IF EXISTS idx_cached_insights_expires;

-- workstream_scans
DROP INDEX IF EXISTS idx_workstream_scans_workstream;
DROP INDEX IF EXISTS idx_workstream_scans_user;
DROP INDEX IF EXISTS idx_workstream_scans_created;

COMMIT;

-- Migration: domain_reputation
-- Created at: 1766739001
-- Task: 0.1 from DEV_PLAN_Information_Quality.md
--
-- PURPOSE:
--   Creates the domain_reputation table to store credibility tiers and
--   user-aggregated reputation for source domains. Each row represents a known
--   domain with its curated tier, crowd-sourced quality ratings, and pipeline
--   triage statistics. A composite_score is derived from weighted combination:
--   50% curated tier + 30% user ratings + 20% pipeline pass rate.
--
-- WHAT DEPENDS ON THIS:
--   - Migration 1766739004 (sources_quality_fields) adds FK to this table
--   - Migration 1766739010 (seed data) populates 100+ curated domains
--   - domain_reputation_service.py reads/writes this table
--   - Discovery pipeline triage uses composite_score for source filtering
--   - SQI calculation engine reads curated_tier and composite_score
--   - Admin UI domain management page reads and writes all columns
--   - source_ratings are aggregated nightly into user_quality_avg/user_relevance_avg
--
-- COMPOSITE SCORE FORMULA (implemented in domain_reputation_service.py):
--   composite_score = (curated_tier_score * 0.50)
--                   + (user_quality_avg_normalized * 0.30)
--                   + (triage_pass_rate * 100 * 0.20)
--                   + texas_relevance_bonus
--
--   Where curated_tier_score: Tier 1 = 85, Tier 2 = 60, Tier 3 = 35, NULL = 20
--   And user_quality_avg_normalized: (user_quality_avg / 5.0) * 100
--
-- ROLLBACK:
--   DROP TRIGGER IF EXISTS trigger_domain_reputation_updated_at ON domain_reputation;
--   DROP INDEX IF EXISTS idx_domain_reputation_category;
--   DROP INDEX IF EXISTS idx_domain_reputation_composite;
--   DROP INDEX IF EXISTS idx_domain_reputation_tier;
--   DROP INDEX IF EXISTS idx_domain_reputation_pattern;
--   DROP TABLE IF EXISTS domain_reputation;
-- ============================================================================

-- ============================================================================
-- TABLE CREATION
-- ============================================================================

CREATE TABLE domain_reputation (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Domain pattern for matching. Supports exact domains ('gartner.com'),
    -- subdomain wildcards ('*.harvard.edu'), and TLD wildcards ('*.gov').
    -- Matching priority in domain_reputation_service.py:
    --   1. Exact match (e.g., 'gartner.com')
    --   2. Parent domain match (e.g., 'research.gartner.com' → 'gartner.com')
    --   3. Subdomain wildcard (e.g., '*.harvard.edu')
    --   4. TLD wildcard (e.g., '*.gov')
    domain_pattern TEXT NOT NULL UNIQUE,

    -- Human-readable organization name for display
    organization_name TEXT NOT NULL,

    -- Category for grouping and filtering in the admin UI and analytics.
    -- Expected values: 'consulting', 'government', 'academic', 'gov_tech_media',
    -- 'federal_state_gov', 'innovation_network', 'professional_association',
    -- 'think_tank', 'international', 'research'
    category TEXT NOT NULL,

    -- Curated credibility tier assigned by project maintainers.
    -- Tier 1 = Authoritative (Gartner, McKinsey, federal agencies)
    -- Tier 2 = Credible (ICMA, Bloomberg Cities, state agencies)
    -- Tier 3 = General (news outlets, trade publications)
    -- NULL = Untiered (not yet reviewed or does not fit tier model)
    curated_tier INTEGER CHECK (curated_tier IN (1, 2, 3)),

    -- Aggregated user quality ratings (1-5 scale, averaged from source_ratings).
    -- Recalculated nightly by domain_reputation_service.recalculate_all().
    user_quality_avg NUMERIC(3,2) DEFAULT 0,

    -- Aggregated user municipal relevance ratings.
    -- Encoded: high=4, medium=3, low=2, not_relevant=1, averaged.
    user_relevance_avg NUMERIC(3,2) DEFAULT 0,

    -- Count of unique user ratings contributing to the averages above.
    user_rating_count INTEGER DEFAULT 0,

    -- Fraction of sources from this domain that passed AI triage (0.0000-1.0000).
    -- Recalculated nightly from discovered_sources data.
    triage_pass_rate NUMERIC(5,4) DEFAULT 0,

    -- Total number of sources from this domain that entered triage.
    triage_total_count INTEGER DEFAULT 0,

    -- Number of sources from this domain that passed triage.
    triage_pass_count INTEGER DEFAULT 0,

    -- Weighted composite score (0-100+). See formula in header comment.
    -- Used as the primary sort/filter criterion for domain credibility.
    composite_score NUMERIC(5,2) DEFAULT 0,

    -- Bonus points for Texas-specific sources (e.g., texas.gov, ut.edu).
    -- Added directly to composite_score. Typically 10 for TX sources, 0 otherwise.
    texas_relevance_bonus INTEGER DEFAULT 0,

    -- Soft-delete flag. Inactive domains are excluded from triage lookups
    -- but retained for historical analytics.
    is_active BOOLEAN DEFAULT TRUE,

    -- Free-text admin notes explaining tier rationale or special handling.
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Primary lookup: match incoming source URLs against domain patterns.
-- The domain_reputation_service extracts the domain from a URL and queries
-- this index for an exact match first, then falls back to parent domain,
-- then wildcard matching.
CREATE INDEX idx_domain_reputation_pattern ON domain_reputation (domain_pattern);

-- Filter by curated tier (e.g., "show all Tier 1 domains"). Partial index
-- excludes untiered rows since they're the majority in a large dataset.
CREATE INDEX idx_domain_reputation_tier ON domain_reputation (curated_tier)
    WHERE curated_tier IS NOT NULL;

-- Sort by composite score descending (e.g., "top domains leaderboard").
CREATE INDEX idx_domain_reputation_composite ON domain_reputation (composite_score DESC);

-- Filter by category (e.g., "all consulting firms" or "all academic sources").
CREATE INDEX idx_domain_reputation_category ON domain_reputation (category);

-- ============================================================================
-- TRIGGER FOR UPDATED_AT
-- ============================================================================

-- Reuse the existing update_updated_at() function from 001_complete_schema.sql.
-- This trigger automatically sets updated_at = NOW() on every UPDATE.
DROP TRIGGER IF EXISTS trigger_domain_reputation_updated_at ON domain_reputation;

CREATE TRIGGER trigger_domain_reputation_updated_at
    BEFORE UPDATE ON domain_reputation
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS (required for Supabase)
ALTER TABLE domain_reputation ENABLE ROW LEVEL SECURITY;

-- SELECT: All authenticated users can view domain reputations.
-- Needed for the methodology page, source detail views, and analytics.
CREATE POLICY "Authenticated users can view domain_reputation"
    ON domain_reputation FOR SELECT
    TO authenticated
    USING (true);

-- INSERT: Only service_role (backend) can add domains.
-- Admin UI will use the service key for domain management.
CREATE POLICY "Service role can insert domain_reputation"
    ON domain_reputation FOR INSERT
    TO service_role
    WITH CHECK (true);

-- UPDATE: Only service_role can update domains.
-- Used by the nightly aggregation job and admin management.
CREATE POLICY "Service role can update domain_reputation"
    ON domain_reputation FOR UPDATE
    TO service_role
    USING (true);

-- DELETE: Only service_role can delete domains.
CREATE POLICY "Service role can delete domain_reputation"
    ON domain_reputation FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- COLUMN COMMENTS
-- ============================================================================

COMMENT ON TABLE domain_reputation IS 'Credibility tiers and aggregated reputation scores for source domains. Used by discovery triage, SQI calculation, and the methodology page.';
COMMENT ON COLUMN domain_reputation.domain_pattern IS 'Domain matching pattern: exact (gartner.com), subdomain wildcard (*.harvard.edu), or TLD wildcard (*.gov)';
COMMENT ON COLUMN domain_reputation.organization_name IS 'Human-readable organization name for UI display';
COMMENT ON COLUMN domain_reputation.category IS 'Organization category: consulting, government, academic, gov_tech_media, etc.';
COMMENT ON COLUMN domain_reputation.curated_tier IS 'Credibility tier: 1=Authoritative, 2=Credible, 3=General, NULL=Untiered';
COMMENT ON COLUMN domain_reputation.composite_score IS 'Weighted score (50% curated + 30% user + 20% pipeline + TX bonus). Primary ranking metric.';
COMMENT ON COLUMN domain_reputation.texas_relevance_bonus IS 'Bonus points (+10) for Texas-specific domains like texas.gov or ut.edu';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

SELECT 'domain_reputation table created successfully' AS status;

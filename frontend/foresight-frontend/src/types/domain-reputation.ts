/**
 * Domain Reputation Types
 *
 * TypeScript interfaces for the domain reputation system that tracks source
 * credibility across the Foresight platform. Maps to the `domain_reputation`
 * database table and its associated API endpoints.
 *
 * The domain reputation system combines three inputs:
 * - **Curated tiers** assigned by editorial staff (50% weight)
 * - **User quality/relevance ratings** aggregated from source_ratings (30% weight)
 * - **Pipeline triage pass rates** computed from discovery outcomes (20% weight)
 *
 * These produce a composite_score used throughout the platform for
 * source filtering, SQI calculation, and the domain leaderboard.
 *
 * @module types/domain-reputation
 */

// =============================================================================
// Domain Reputation Response Types
// =============================================================================

/**
 * Full domain reputation record returned by the API.
 *
 * Includes both curated editorial data and computed metrics derived from
 * user ratings and triage history. Corresponds to the
 * `DomainReputationResponse` Pydantic model on the backend.
 */
export interface DomainReputation {
  /** UUID of the domain reputation record */
  id: string;
  /** Domain matching pattern: exact ('gartner.com'), subdomain wildcard ('*.harvard.edu'), or TLD wildcard ('*.gov') */
  domain_pattern: string;
  /** Human-readable organization name for UI display */
  organization_name: string;
  /** Organization category (e.g., 'consulting', 'government', 'academic', 'gov_tech_media', 'think_tank') */
  category: string;
  /** Credibility tier: 1=Authoritative, 2=Credible, 3=General, null=Untiered */
  curated_tier: number | null;
  /** Average user quality rating across all raters (1.0-5.0 scale) */
  user_quality_avg: number;
  /** Average user relevance rating (encoded: high=4, medium=3, low=2, not_relevant=1) */
  user_relevance_avg: number;
  /** Total number of unique user ratings for this domain */
  user_rating_count: number;
  /** Fraction of sources from this domain that passed AI triage (0.0-1.0) */
  triage_pass_rate: number;
  /** Total number of sources from this domain that entered triage */
  triage_total_count: number;
  /** Number of sources from this domain that passed triage */
  triage_pass_count: number;
  /** Weighted composite score: 50% curated tier + 30% user ratings + 20% pipeline + TX bonus (0-100+) */
  composite_score: number;
  /** Bonus points for Texas/Austin-specific domains (0-20, typically 10 for TX sources) */
  texas_relevance_bonus: number;
  /** Whether this domain is actively tracked; inactive domains are excluded from triage lookups */
  is_active: boolean;
  /** Free-text admin notes explaining tier rationale or special handling */
  notes: string | null;
  /** ISO 8601 timestamp when the domain record was created */
  created_at: string;
  /** ISO 8601 timestamp when the domain record was last updated */
  updated_at: string;
}

// =============================================================================
// Domain Reputation Request Types
// =============================================================================

/**
 * Payload for creating a new domain reputation record.
 *
 * Used by administrators to seed the domain reputation table with
 * curated editorial assessments. Computed fields (user ratings, triage stats,
 * composite score) are initialized to defaults by the backend.
 */
export interface DomainReputationCreate {
  /** Domain matching pattern (e.g., 'gartner.com', '*.gov') */
  domain_pattern: string;
  /** Human-readable organization name */
  organization_name: string;
  /** Organization category (e.g., 'consulting', 'government', 'academic') */
  category: string;
  /** Credibility tier: 1=Authoritative, 2=Credible, 3=General */
  curated_tier?: number | null;
  /** Bonus points for Texas/Austin-specific domains (0-20) */
  texas_relevance_bonus?: number;
  /** Free-text admin notes */
  notes?: string | null;
}

/**
 * Payload for updating an existing domain reputation record.
 *
 * All fields are optional -- only provided fields are updated.
 * Computed aggregation fields (user ratings, triage stats) are not
 * directly editable; they are recalculated by the nightly aggregation job.
 */
export interface DomainReputationUpdate {
  /** Updated organization name */
  organization_name?: string;
  /** Updated source category */
  category?: string;
  /** Updated credibility tier: 1=Authoritative, 2=Credible, 3=General */
  curated_tier?: number | null;
  /** Updated Texas relevance bonus (0-20) */
  texas_relevance_bonus?: number;
  /** Whether this domain should be actively tracked */
  is_active?: boolean;
  /** Updated editorial notes */
  notes?: string | null;
}

// =============================================================================
// Domain Reputation Aggregation Types
// =============================================================================

/**
 * Leaderboard entry for top-scoring domains.
 *
 * A subset of DomainReputation fields used to render the domain reputation
 * leaderboard, showing the highest-scoring domains by composite score.
 * Returned by the `GET /api/v1/domain-reputation/top` endpoint.
 */
export interface TopDomain {
  /** UUID of the domain reputation record */
  id: string;
  /** Domain matching pattern */
  domain_pattern: string;
  /** Human-readable organization name */
  organization_name: string;
  /** Organization category */
  category: string;
  /** Credibility tier: 1=Authoritative, 2=Credible, 3=General, null=Untiered */
  curated_tier: number | null;
  /** Weighted composite reputation score (0-100+) */
  composite_score: number;
  /** Average user quality rating (1.0-5.0 scale) */
  user_quality_avg: number;
  /** Total number of user ratings */
  user_rating_count: number;
  /** Fraction of sources passing triage (0.0-1.0) */
  triage_pass_rate: number;
}

/**
 * Paginated list response for domain reputation records.
 *
 * Used by admin views that list all tracked domains with pagination.
 * Returned by the `GET /api/v1/domain-reputation` endpoint.
 */
export interface DomainReputationList {
  /** List of domain reputation records for the current page */
  items: DomainReputation[];
  /** Total number of matching records across all pages */
  total: number;
  /** Current page number (1-based) */
  page: number;
  /** Number of items per page */
  page_size: number;
}

// =============================================================================
// Quality Breakdown Types (SQI Component Scores)
// =============================================================================

/**
 * Quality tier classification based on SQI score ranges.
 *
 * - `high`: SQI 75-100 -- authoritative, well-corroborated sources
 * - `moderate`: SQI 50-74 -- credible sources with some gaps
 * - `needs_verification`: SQI 0-49 -- limited or unverified sourcing
 */
export type QualityTier = "high" | "moderate" | "needs_verification";

/**
 * Full Source Quality Index (SQI) breakdown for an intelligence card.
 *
 * Provides the composite quality score along with individual component
 * scores that contribute to the overall SQI. Used to render the quality
 * breakdown panel in the card detail view.
 *
 * The SQI is computed from five weighted components:
 * - source_authority (30%): domain reputation composite score
 * - source_diversity (20%): variety of source types
 * - corroboration (20%): number of independent source clusters
 * - recency (15%): freshness of contributing sources
 * - municipal_specificity (15%): relevance to municipal operations
 */
export interface QualityBreakdown {
  /** Composite SQI score (0-100) */
  quality_score: number;
  /** Quality tier classification derived from the score */
  quality_tier: QualityTier;
  /** Domain reputation score component (0-100) */
  source_authority: number;
  /** Source type variety score component (0-100) */
  source_diversity: number;
  /** Independent story cluster count score component (0-100) */
  corroboration: number;
  /** Source freshness score component (0-100) */
  recency: number;
  /** Municipal relevance score component (0-100) */
  municipal_specificity: number;
  /** Total number of sources contributing to this card's quality score */
  source_count: number;
  /** Number of independent source clusters identified */
  cluster_count: number;
  /** ISO 8601 timestamp when the SQI was last calculated, or null if never calculated */
  calculated_at: string | null;
}

/**
 * Filter parameters for quality tier-based card filtering.
 *
 * Used as query parameters on card listing endpoints to filter
 * by quality tier or score range.
 */
export interface QualityTierFilter {
  /** Filter by quality tier classification */
  tier?: QualityTier;
  /** Minimum SQI score (0-100) */
  min_score?: number;
  /** Maximum SQI score (0-100) */
  max_score?: number;
}

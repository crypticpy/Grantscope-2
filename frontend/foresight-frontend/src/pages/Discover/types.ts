/**
 * Discover Page Types
 *
 * TypeScript interfaces and type definitions for the Discover page.
 * These types support the card grid, filtering, sorting, and search
 * functionality on the main discovery interface.
 *
 * @module pages/Discover/types
 */

/**
 * Card data structure for display on the Discover page.
 *
 * Represents an intelligence card with all metadata needed for rendering,
 * filtering, and sorting in the card grid. Includes quality-related fields
 * from the Information Quality system.
 */
export interface Card {
  /** Unique card identifier (UUID) */
  id: string;
  /** Display name of the intelligence card */
  name: string;
  /** URL-friendly slug for routing */
  slug: string;
  /** Brief text summary of the card topic */
  summary: string;
  /** Associated strategic pillar code (e.g., 'CH', 'MC', 'HS') */
  pillar_id: string;
  /** Maturity stage identifier (1-8) */
  stage_id: string;
  /** Technology horizon classification */
  horizon: "H1" | "H2" | "H3";
  /** Novelty score (0-100) */
  novelty_score: number;
  /** Maturity score (0-100) */
  maturity_score: number;
  /** Impact score (0-100) */
  impact_score: number;
  /** Relevance score (0-100) */
  relevance_score: number;
  /** Velocity score (0-100) */
  velocity_score: number;
  /** Risk score (0-100) */
  risk_score: number;
  /** Opportunity score (0-100) */
  opportunity_score: number;
  /** ISO 8601 timestamp when the card was created */
  created_at: string;
  /** ISO 8601 timestamp when the card was last updated */
  updated_at?: string;
  /** Reference to an anchor card for derived cards */
  anchor_id?: string;
  /** CMO Top 25 priority alignment codes */
  top25_relevance?: string[];
  /** Vector similarity score (0-1) -- populated when semantic search is used */
  search_relevance?: number;
  /** Source Quality Index composite score (0-100), null if not yet calculated */
  signal_quality_score?: number | null;
  /** Origin of the card: how it was created */
  origin?: "discovery" | "user_created" | "workstream_scan" | "manual";
  /** Whether this card is exploratory (not tied to a specific strategic pillar) */
  is_exploratory?: boolean;
  /** Discovery metadata including score verification info */
  discovery_metadata?: DiscoveryMetadata;
}

/**
 * Metadata attached to cards by the discovery pipeline.
 *
 * Contains flags and contextual information about how the card was
 * created and whether its scores have been verified by AI analysis.
 */
export interface DiscoveryMetadata {
  /** Whether the card's scores are AI-assigned defaults that have not been verified */
  scores_are_defaults?: boolean;
  /** Additional metadata properties from the discovery pipeline */
  [key: string]: unknown;
}

/**
 * Strategic pillar data structure.
 *
 * Represents one of Austin's strategic framework pillars used for
 * categorizing intelligence cards.
 */
export interface Pillar {
  /** Pillar identifier code (e.g., 'CH', 'MC') */
  id: string;
  /** Human-readable pillar name (e.g., 'Community Health') */
  name: string;
  /** Display color for the pillar badge (hex or Tailwind class) */
  color: string;
}

/**
 * Maturity stage data structure.
 *
 * Represents a stage in the technology maturity lifecycle
 * (Concept through Declining).
 */
export interface Stage {
  /** Stage identifier */
  id: string;
  /** Human-readable stage name (e.g., 'Concept', 'Pilot', 'Scaling') */
  name: string;
  /** Sort position for ordering stages in the lifecycle progression */
  sort_order: number;
}

/**
 * Sort options for card ordering in the Discover grid.
 *
 * Each option maps to a database column and sort direction
 * in the `getSortConfig` utility function.
 */
export type SortOption =
  | "newest"
  | "oldest"
  | "recently_updated"
  | "least_recently_updated"
  | "signal_quality_score";

/**
 * Filter state object used for debounced search and score filtering.
 *
 * All filter values are combined with AND logic when querying cards.
 */
export interface FilterState {
  /** Text search term matched against card name and summary */
  searchTerm: string;
  /** Minimum impact score threshold (0-100) */
  impactMin: number;
  /** Minimum relevance score threshold (0-100) */
  relevanceMin: number;
  /** Minimum novelty score threshold (0-100) */
  noveltyMin: number;
}

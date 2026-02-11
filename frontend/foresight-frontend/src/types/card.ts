/**
 * Shared Card Type Definitions
 *
 * Canonical card interfaces used across Dashboard, Discover, Signals,
 * and Kanban views. Import from here instead of re-declaring per-page
 * to keep field names (e.g. signal_quality_score) in sync.
 */

/** Technology horizon classification. */
export type Horizon = "H1" | "H2" | "H3";

/** How a card was created. */
export type CardOrigin =
  | "discovery"
  | "user_created"
  | "workstream_scan"
  | "manual";

/**
 * Base card fields shared by every view.
 *
 * Individual pages extend this with view-specific extras
 * (e.g. search_relevance for Discover, personal metadata for Signals).
 */
export interface BaseCard {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: Horizon;
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  created_at: string;
  updated_at?: string;
  top25_relevance?: string[];
  signal_quality_score?: number | null;
}

/**
 * Full card with all optional metadata.
 * Used by Discover and Dashboard where `select("*")` returns everything.
 */
export interface FullCard extends BaseCard {
  risk_score: number;
  opportunity_score: number;
  anchor_id?: string;
  search_relevance?: number;
  origin?: CardOrigin;
  is_exploratory?: boolean;
  source_count?: number;
  discovery_metadata?: DiscoveryMetadata;
}

/**
 * Embedded card subset used inside workstream kanban cards.
 * Contains only the fields the kanban UI actually renders.
 */
export interface EmbeddedCard extends BaseCard {
  is_exploratory?: boolean;
}

/**
 * Metadata attached to cards by the discovery pipeline.
 */
export interface DiscoveryMetadata {
  scores_are_defaults?: boolean;
  [key: string]: unknown;
}

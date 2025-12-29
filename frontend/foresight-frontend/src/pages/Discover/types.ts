/**
 * Discover Page Types
 *
 * TypeScript interfaces and type definitions for the Discover page.
 */

/**
 * Card data structure for display
 */
export interface Card {
  id: string;
  name: string;
  slug: string;
  summary: string;
  pillar_id: string;
  stage_id: string;
  horizon: 'H1' | 'H2' | 'H3';
  novelty_score: number;
  maturity_score: number;
  impact_score: number;
  relevance_score: number;
  velocity_score: number;
  risk_score: number;
  opportunity_score: number;
  created_at: string;
  updated_at?: string;
  anchor_id?: string;
  top25_relevance?: string[];
  /** Vector similarity score (0-1) - populated when semantic search is used */
  search_relevance?: number;
}

/**
 * Pillar data structure
 */
export interface Pillar {
  id: string;
  name: string;
  color: string;
}

/**
 * Stage data structure
 */
export interface Stage {
  id: string;
  name: string;
  sort_order: number;
}

/**
 * Sort options for card ordering
 */
export type SortOption = 'newest' | 'oldest' | 'recently_updated' | 'least_recently_updated';

/**
 * Filter state object for debouncing
 */
export interface FilterState {
  searchTerm: string;
  impactMin: number;
  relevanceMin: number;
  noveltyMin: number;
}
